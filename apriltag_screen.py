"""
AprilTag-based screen registration with homography mapping.

Uses tag36h11 family with specific tag IDs at each corner:
- ID 0: Top-left
- ID 1: Top-right
- ID 2: Bottom-right
- ID 3: Bottom-left
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from pupil_apriltags import Detector


@dataclass
class ScreenConfig:
    """Screen configuration."""
    width: int = 1920
    height: int = 1080
    # Tag IDs for each corner (clockwise from top-left)
    tag_ids: tuple[int, int, int, int] = (0, 1, 2, 3)


class AprilTagScreenMapper:
    """
    Detects AprilTags at screen corners and computes homography
    for mapping camera coordinates to screen coordinates.
    """

    def __init__(self, config: Optional[ScreenConfig] = None):
        self.config = config or ScreenConfig()
        self.detector = Detector(
            families="tag36h11",
            nthreads=4,
            quad_decimate=1.0,
            quad_sigma=0.0,
            refine_edges=True,
            decode_sharpening=0.25,
        )
        self.homography: Optional[np.ndarray] = None
        self.inverse_homography: Optional[np.ndarray] = None
        self._last_tag_centers: dict[int, np.ndarray] = {}

        # Screen corner coordinates (destination points)
        self.screen_corners = np.array([
            [0, 0],                                      # Top-left
            [self.config.width, 0],                      # Top-right
            [self.config.width, self.config.height],    # Bottom-right
            [0, self.config.height],                    # Bottom-left
        ], dtype=np.float32)

    def detect_tags(self, frame: np.ndarray) -> dict[int, np.ndarray]:
        """
        Detect AprilTags in frame and return their centers.
        
        Args:
            frame: BGR image from camera
            
        Returns:
            Dictionary mapping tag_id -> center coordinates (x, y)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detections = self.detector.detect(gray)

        tag_centers = {}
        for det in detections:
            if det.tag_id in self.config.tag_ids:
                # det.center is (x, y) of tag center
                tag_centers[det.tag_id] = np.array(det.center, dtype=np.float32)

        self._last_tag_centers = tag_centers
        return tag_centers

    def compute_homography(self, tag_centers: dict[int, np.ndarray]) -> bool:
        """
        Compute homography matrix from detected tag centers.
        
        Args:
            tag_centers: Dictionary mapping tag_id -> center coordinates
            
        Returns:
            True if homography was successfully computed (all 4 tags found)
        """
        # Check if all 4 tags are detected
        if not all(tid in tag_centers for tid in self.config.tag_ids):
            return False

        # Source points from camera (tag centers in order: TL, TR, BR, BL)
        src_points = np.array([
            tag_centers[self.config.tag_ids[0]],  # Top-left
            tag_centers[self.config.tag_ids[1]],  # Top-right
            tag_centers[self.config.tag_ids[2]],  # Bottom-right
            tag_centers[self.config.tag_ids[3]],  # Bottom-left
        ], dtype=np.float32)

        # Compute homography: camera -> screen
        self.homography, _ = cv2.findHomography(src_points, self.screen_corners)
        
        if self.homography is not None:
            self.inverse_homography = np.linalg.inv(self.homography)
            return True
        return False

    def camera_to_screen(self, point: tuple[float, float]) -> Optional[tuple[int, int]]:
        """
        Map a point from camera coordinates to screen coordinates.
        
        Args:
            point: (x, y) coordinates in camera frame
            
        Returns:
            (x, y) screen coordinates, or None if homography not available
        """
        if self.homography is None:
            return None

        # Convert to homogeneous coordinates
        pt = np.array([[point[0], point[1], 1.0]], dtype=np.float32).T
        
        # Apply homography
        transformed = self.homography @ pt
        
        # Convert back from homogeneous coordinates
        w = transformed[2, 0]
        if abs(w) < 1e-10:
            return None
            
        screen_x = int(transformed[0, 0] / w)
        screen_y = int(transformed[1, 0] / w)

        return (screen_x, screen_y)

    def screen_to_camera(self, point: tuple[float, float]) -> Optional[tuple[int, int]]:
        """
        Map a point from screen coordinates to camera coordinates.
        
        Args:
            point: (x, y) coordinates on screen
            
        Returns:
            (x, y) camera coordinates, or None if homography not available
        """
        if self.inverse_homography is None:
            return None

        pt = np.array([[point[0], point[1], 1.0]], dtype=np.float32).T
        transformed = self.inverse_homography @ pt
        
        w = transformed[2, 0]
        if abs(w) < 1e-10:
            return None
            
        cam_x = int(transformed[0, 0] / w)
        cam_y = int(transformed[1, 0] / w)

        return (cam_x, cam_y)

    def is_point_on_screen(self, screen_point: tuple[int, int]) -> bool:
        """Check if a screen point is within display bounds."""
        x, y = screen_point
        return 0 <= x < self.config.width and 0 <= y < self.config.height

    def draw_debug(self, frame: np.ndarray) -> np.ndarray:
        """
        Draw debug visualization on frame.
        
        Args:
            frame: BGR image from camera
            
        Returns:
            Frame with debug overlays
        """
        debug_frame = frame.copy()

        # Draw detected tag centers
        for tag_id, center in self._last_tag_centers.items():
            cx, cy = int(center[0]), int(center[1])
            cv2.circle(debug_frame, (cx, cy), 10, (0, 255, 0), -1)
            cv2.putText(
                debug_frame, f"ID:{tag_id}",
                (cx + 15, cy), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (0, 255, 0), 2
            )

        # Draw quadrilateral if all 4 tags detected
        if len(self._last_tag_centers) == 4:
            pts = np.array([
                self._last_tag_centers[self.config.tag_ids[i]]
                for i in range(4)
            ], dtype=np.int32)
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
    mapper = AprilTagScreenMapper()
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print("Error: Could not open camera")
        return

    print("AprilTag Screen Registration Demo")
    print("==================================")
    print("Place tag36h11 AprilTags at screen corners:")
    print("  ID 0: Top-left")
    print("  ID 1: Top-right")
    print("  ID 2: Bottom-right")
    print("  ID 3: Bottom-left")
    print()
    print("Controls:")
    print("  'q' - Quit")
    print("  'c' - Lock/unlock calibration")
    print("  Click - Show mapped screen coordinates")

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
            break

        # Detect tags
        tag_centers = mapper.detect_tags(frame)

        # Update homography (unless locked)
        if not calibration_locked:
            mapper.compute_homography(tag_centers)

        # Draw debug visualization
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

        # Lock status
        if calibration_locked:
            cv2.putText(
                debug_frame, "LOCKED",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (255, 165, 0), 2
            )

        cv2.imshow("AprilTag Screen Registration", debug_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            calibration_locked = not calibration_locked
            print(f"Calibration {'locked' if calibration_locked else 'unlocked'}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_demo()
