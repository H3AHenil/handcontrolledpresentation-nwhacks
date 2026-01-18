"""
AprilTag-based screen registration with homography mapping (tag16h5).

Tags are placed at screen corners. We use the INNER corner of each tag
(the corner facing the screen center) for accurate mapping.

Tag placement:
- ID 0: Top-left corner     → use tag's bottom-right corner
- ID 1: Top-right corner    → use tag's bottom-left corner
- ID 2: Bottom-right corner → use tag's top-left corner
- ID 3: Bottom-left corner  → use tag's top-right corner
"""

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from pupil_apriltags import Detector

# Corner indices in AprilTag detection (counter-clockwise from bottom-left)
# corners[0] = bottom-left, corners[1] = bottom-right
# corners[2] = top-right, corners[3] = top-left
CORNER_BOTTOM_LEFT = 0
CORNER_BOTTOM_RIGHT = 1
CORNER_TOP_RIGHT = 2
CORNER_TOP_LEFT = 3

# Which corner of each tag faces the screen center
INNER_CORNER_MAP = {
    0: CORNER_BOTTOM_RIGHT,  # Top-left tag → bottom-right corner
    1: CORNER_BOTTOM_LEFT,   # Top-right tag → bottom-left corner
    2: CORNER_TOP_LEFT,      # Bottom-right tag → top-left corner
    3: CORNER_TOP_RIGHT,     # Bottom-left tag → top-right corner
}


@dataclass
class ScreenConfig:
    """Screen configuration."""
    width: int = 1920
    height: int = 1080
    tag_ids: tuple[int, int, int, int] = (0, 1, 2, 3)


class AprilTagScreenMapper:
    """
    Detects AprilTags at screen corners and computes homography
    for mapping camera coordinates to screen coordinates.
    """

    def __init__(self, config: Optional[ScreenConfig] = None, smoothing: float = 0.7):
        """
        Args:
            config: Screen configuration
            smoothing: Temporal smoothing factor (0=no smoothing, 1=full smoothing)
        """
        self.config = config or ScreenConfig()
        self.smoothing = smoothing
        
        self.detector = Detector(
            families="tag16h5",
            nthreads=4,
            quad_decimate=1.0,
            quad_sigma=0.0,
            refine_edges=True,
            decode_sharpening=0.25,
        )
        
        self.homography: Optional[np.ndarray] = None
        self.inverse_homography: Optional[np.ndarray] = None
        self._last_detections: dict[int, object] = {}
        self._smoothed_corners: Optional[np.ndarray] = None

        # Screen corner coordinates (destination points)
        self.screen_corners = np.array([
            [0, 0],
            [self.config.width - 1, 0],
            [self.config.width - 1, self.config.height - 1],
            [0, self.config.height - 1],
        ], dtype=np.float32)

    def detect_tags(self, frame: np.ndarray) -> dict[int, object]:
        """
        Detect AprilTags in frame.
        
        Returns:
            Dictionary mapping tag_id -> detection object (with corners attribute)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detections = self.detector.detect(gray)

        tag_detections = {}
        for det in detections:
            if det.tag_id in self.config.tag_ids:
                tag_detections[det.tag_id] = det

        self._last_detections = tag_detections
        return tag_detections

    def _get_inner_corners(self, detections: dict[int, object]) -> Optional[np.ndarray]:
        """Extract the inner corners from detected tags."""
        if not all(tid in detections for tid in self.config.tag_ids):
            return None

        corners = []
        for tag_id in self.config.tag_ids:
            det = detections[tag_id]
            corner_idx = INNER_CORNER_MAP[tag_id]
            corner = det.corners[corner_idx]
            corners.append(corner)

        return np.array(corners, dtype=np.float32)

    def compute_homography(self, detections: dict[int, object]) -> bool:
        """
        Compute homography matrix from detected tags.
        
        Uses the inner corners of tags for better accuracy.
        """
        src_corners = self._get_inner_corners(detections)
        if src_corners is None:
            return False

        # Apply temporal smoothing
        if self._smoothed_corners is None:
            self._smoothed_corners = src_corners.copy()
        else:
            self._smoothed_corners = (
                self.smoothing * self._smoothed_corners +
                (1 - self.smoothing) * src_corners
            )

        # Use getPerspectiveTransform for exactly 4 points (more stable than findHomography)
        self.homography = cv2.getPerspectiveTransform(
            self._smoothed_corners, self.screen_corners
        )

        if self.homography is not None:
            self.inverse_homography = cv2.getPerspectiveTransform(
                self.screen_corners, self._smoothed_corners
            )
            return True
        return False

    def camera_to_screen(self, point: tuple[float, float]) -> Optional[tuple[int, int]]:
        """Map a point from camera coordinates to screen coordinates."""
        if self.homography is None:
            return None

        # Use OpenCV's perspectiveTransform for accuracy
        pts = np.array([[[point[0], point[1]]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pts, self.homography)
        
        screen_x = int(round(transformed[0, 0, 0]))
        screen_y = int(round(transformed[0, 0, 1]))

        return (screen_x, screen_y)

    def screen_to_camera(self, point: tuple[float, float]) -> Optional[tuple[int, int]]:
        """Map a point from screen coordinates to camera coordinates."""
        if self.inverse_homography is None:
            return None

        pts = np.array([[[point[0], point[1]]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pts, self.inverse_homography)
        
        cam_x = int(round(transformed[0, 0, 0]))
        cam_y = int(round(transformed[0, 0, 1]))

        return (cam_x, cam_y)

    def is_point_on_screen(self, screen_point: tuple[int, int]) -> bool:
        """Check if a screen point is within display bounds."""
        x, y = screen_point
        return 0 <= x < self.config.width and 0 <= y < self.config.height

    def draw_debug(self, frame: np.ndarray) -> np.ndarray:
        """Draw debug visualization on frame."""
        debug_frame = frame.copy()

        for tag_id, det in self._last_detections.items():
            # Draw all 4 corners of tag (small dots)
            for i, corner in enumerate(det.corners):
                cx, cy = int(corner[0]), int(corner[1])
                cv2.circle(debug_frame, (cx, cy), 3, (100, 100, 100), -1)

            # Draw the inner corner we use (larger, green)
            inner_idx = INNER_CORNER_MAP[tag_id]
            inner_corner = det.corners[inner_idx]
            ix, iy = int(inner_corner[0]), int(inner_corner[1])
            cv2.circle(debug_frame, (ix, iy), 8, (0, 255, 0), -1)
            
            # Draw tag center and ID
            cx, cy = int(det.center[0]), int(det.center[1])
            cv2.putText(
                debug_frame, f"ID:{tag_id}",
                (cx + 15, cy), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (0, 255, 0), 2
            )

        # Draw quadrilateral connecting inner corners
        if self._smoothed_corners is not None and len(self._last_detections) == 4:
            pts = self._smoothed_corners.astype(np.int32)
            cv2.polylines(debug_frame, [pts], True, (255, 0, 255), 2)

        # Status text
        status = "CALIBRATED" if self.homography is not None else "SEARCHING..."
        color = (0, 255, 0) if self.homography is not None else (0, 0, 255)
        cv2.putText(
            debug_frame, status,
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
            1.0, color, 2
        )

        return debug_frame


def run_demo(camera_index: int = 0):
    """Run interactive demo with camera feed."""
    import time

    mapper = AprilTagScreenMapper(smoothing=0.5)

    print(f"Opening camera {camera_index}...")
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print("Error: Could not open camera")
        print("  - Check camera permissions in System Settings > Privacy > Camera")
        print("  - Make sure no other app is using the camera")
        return

    time.sleep(0.5)

    ret, test_frame = cap.read()
    if not ret or test_frame is None:
        print("Error: Camera opened but cannot read frames")
        print("  - Try closing other apps that might use the camera")
        print("  - Try a different camera index: python apriltag_screen.py --camera 1")
        cap.release()
        return

    print("Camera ready!")
    print()
    print("AprilTag Screen Registration Demo (tag16h5)")
    print("=" * 45)
    print("Place tags at screen corners (inner corner touches screen edge):")
    print("  ID 0: Top-left")
    print("  ID 1: Top-right")
    print("  ID 2: Bottom-right")
    print("  ID 3: Bottom-left")
    print()
    print("Controls:")
    print("  'q' - Quit")
    print("  'c' - Lock/unlock calibration")
    print("  's' - Toggle smoothing")

    calibration_locked = False
    mouse_pos = None

    def mouse_callback(event, x, y, flags, param):
        nonlocal mouse_pos
        if event == cv2.EVENT_MOUSEMOVE:
            mouse_pos = (x, y)

    cv2.namedWindow("AprilTag Screen Registration")
    cv2.setMouseCallback("AprilTag Screen Registration", mouse_callback)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Lost camera feed")
            break

        detections = mapper.detect_tags(frame)

        if not calibration_locked:
            mapper.compute_homography(detections)

        debug_frame = mapper.draw_debug(frame)

        # Show mouse position mapping
        if mouse_pos and mapper.homography is not None:
            screen_pt = mapper.camera_to_screen(mouse_pos)
            if screen_pt:
                on_screen = mapper.is_point_on_screen(screen_pt)
                color = (0, 255, 0) if on_screen else (0, 165, 255)
                cv2.circle(debug_frame, mouse_pos, 8, color, -1)
                cv2.putText(
                    debug_frame,
                    f"Screen: ({screen_pt[0]}, {screen_pt[1]})",
                    (mouse_pos[0] + 15, mouse_pos[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
                )

        # Status overlay
        if calibration_locked:
            cv2.putText(
                debug_frame, "LOCKED",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (255, 165, 0), 2
            )

        cv2.putText(
            debug_frame, f"Smoothing: {mapper.smoothing:.1f}",
            (10, debug_frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1
        )

        cv2.imshow("AprilTag Screen Registration", debug_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            calibration_locked = not calibration_locked
            print(f"Calibration {'locked' if calibration_locked else 'unlocked'}")
        elif key == ord('s'):
            mapper.smoothing = 0.0 if mapper.smoothing > 0 else 0.5
            mapper._smoothed_corners = None
            print(f"Smoothing: {mapper.smoothing}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AprilTag screen registration (tag16h5)")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--width", type=int, default=1920, help="Screen width (default: 1920)")
    parser.add_argument("--height", type=int, default=1080, help="Screen height (default: 1080)")
    args = parser.parse_args()

    config = ScreenConfig(width=args.width, height=args.height)
    # Note: config not currently passed to run_demo, would need refactoring for that
    run_demo(camera_index=args.camera)
