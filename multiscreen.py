"""
Multi-screen AprilTag registration system (tag16h5).

Each screen has 4 AprilTags at its corners with unique IDs.
Maximum 7 screens supported (30 tags / 4 per screen).

Example setup with 2 monitors:
    Screen 0 (left):  Tags 0, 1, 2, 3
    Screen 1 (right): Tags 4, 5, 6, 7
"""

from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
from pupil_apriltags import Detector


@dataclass
class ScreenRegion:
    """Configuration for a single screen/monitor."""
    name: str
    width: int
    height: int
    # Tag IDs: [top-left, top-right, bottom-right, bottom-left]
    tag_ids: tuple[int, int, int, int]
    # Global offset (for virtual desktop coordinates)
    offset_x: int = 0
    offset_y: int = 0


@dataclass
class MultiScreenConfig:
    """Configuration for multiple screens."""
    screens: list[ScreenRegion] = field(default_factory=list)

    @classmethod
    def dual_horizontal(cls, width: int = 1920, height: int = 1080) -> "MultiScreenConfig":
        """Create config for 2 side-by-side monitors."""
        return cls(screens=[
            ScreenRegion(name="Left", width=width, height=height,
                        tag_ids=(0, 1, 2, 3), offset_x=0, offset_y=0),
            ScreenRegion(name="Right", width=width, height=height,
                        tag_ids=(4, 5, 6, 7), offset_x=width, offset_y=0),
        ])

    @classmethod
    def dual_vertical(cls, width: int = 1920, height: int = 1080) -> "MultiScreenConfig":
        """Create config for 2 stacked monitors."""
        return cls(screens=[
            ScreenRegion(name="Top", width=width, height=height,
                        tag_ids=(0, 1, 2, 3), offset_x=0, offset_y=0),
            ScreenRegion(name="Bottom", width=width, height=height,
                        tag_ids=(4, 5, 6, 7), offset_x=0, offset_y=height),
        ])

    @classmethod
    def triple_horizontal(cls, width: int = 1920, height: int = 1080) -> "MultiScreenConfig":
        """Create config for 3 side-by-side monitors."""
        return cls(screens=[
            ScreenRegion(name="Left", width=width, height=height,
                        tag_ids=(0, 1, 2, 3), offset_x=0, offset_y=0),
            ScreenRegion(name="Center", width=width, height=height,
                        tag_ids=(4, 5, 6, 7), offset_x=width, offset_y=0),
            ScreenRegion(name="Right", width=width, height=height,
                        tag_ids=(8, 9, 10, 11), offset_x=width * 2, offset_y=0),
        ])


@dataclass
class ScreenState:
    """Runtime state for a single screen."""
    region: ScreenRegion
    homography: Optional[np.ndarray] = None
    inverse_homography: Optional[np.ndarray] = None
    tag_centers: dict[int, np.ndarray] = field(default_factory=dict)
    calibrated: bool = False

    @property
    def screen_corners(self) -> np.ndarray:
        """Local screen corner coordinates (before offset)."""
        return np.array([
            [0, 0],
            [self.region.width, 0],
            [self.region.width, self.region.height],
            [0, self.region.height],
        ], dtype=np.float32)


class MultiScreenMapper:
    """
    Detects AprilTags for multiple screens and maps camera
    coordinates to the appropriate screen.
    """

    def __init__(self, config: MultiScreenConfig):
        self.config = config
        self.detector = Detector(
            families="tag16h5",
            nthreads=4,
            quad_decimate=1.0,
            quad_sigma=0.0,
            refine_edges=True,
            decode_sharpening=0.25,
        )
        
        # Initialize state for each screen
        self.screens: list[ScreenState] = [
            ScreenState(region=region) for region in config.screens
        ]
        
        # Map tag_id -> screen index for quick lookup
        self._tag_to_screen: dict[int, int] = {}
        for idx, region in enumerate(config.screens):
            for tag_id in region.tag_ids:
                self._tag_to_screen[tag_id] = idx

    def detect_tags(self, frame: np.ndarray) -> dict[int, np.ndarray]:
        """Detect all AprilTags in frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detections = self.detector.detect(gray)

        all_centers = {}
        for det in detections:
            if det.tag_id in self._tag_to_screen:
                all_centers[det.tag_id] = np.array(det.center, dtype=np.float32)

        # Distribute to screens
        for screen in self.screens:
            screen.tag_centers = {
                tid: all_centers[tid]
                for tid in screen.region.tag_ids
                if tid in all_centers
            }

        return all_centers

    def compute_homographies(self) -> int:
        """
        Compute homography for each screen that has all 4 tags visible.
        
        Returns:
            Number of screens successfully calibrated
        """
        calibrated_count = 0

        for screen in self.screens:
            # Check if all 4 tags detected
            if not all(tid in screen.tag_centers for tid in screen.region.tag_ids):
                screen.calibrated = False
                continue

            # Source points from camera
            src_points = np.array([
                screen.tag_centers[tid] for tid in screen.region.tag_ids
            ], dtype=np.float32)

            # Compute homography
            screen.homography, _ = cv2.findHomography(src_points, screen.screen_corners)

            if screen.homography is not None:
                screen.inverse_homography = np.linalg.inv(screen.homography)
                screen.calibrated = True
                calibrated_count += 1
            else:
                screen.calibrated = False

        return calibrated_count

    def camera_to_screen(
        self,
        point: tuple[float, float],
    ) -> Optional[tuple[str, int, int, int, int]]:
        """
        Map camera point to screen coordinates.
        
        Returns:
            Tuple of (screen_name, local_x, local_y, global_x, global_y)
            or None if point isn't on any calibrated screen.
        """
        for screen in self.screens:
            if not screen.calibrated:
                continue

            # Transform point
            pt = np.array([[point[0], point[1], 1.0]], dtype=np.float32).T
            transformed = screen.homography @ pt
            
            w = transformed[2, 0]
            if abs(w) < 1e-10:
                continue

            local_x = transformed[0, 0] / w
            local_y = transformed[1, 0] / w

            # Check if point is within this screen's bounds
            if 0 <= local_x < screen.region.width and 0 <= local_y < screen.region.height:
                global_x = int(local_x) + screen.region.offset_x
                global_y = int(local_y) + screen.region.offset_y
                return (
                    screen.region.name,
                    int(local_x),
                    int(local_y),
                    global_x,
                    global_y,
                )

        return None

    def get_calibration_status(self) -> dict[str, bool]:
        """Get calibration status for each screen."""
        return {screen.region.name: screen.calibrated for screen in self.screens}

    def draw_debug(self, frame: np.ndarray) -> np.ndarray:
        """Draw debug visualization."""
        debug_frame = frame.copy()

        colors = [
            (0, 255, 0),    # Green
            (255, 165, 0),  # Orange
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
        ]

        for idx, screen in enumerate(self.screens):
            color = colors[idx % len(colors)]

            # Draw tag centers
            for tag_id, center in screen.tag_centers.items():
                cx, cy = int(center[0]), int(center[1])
                cv2.circle(debug_frame, (cx, cy), 10, color, -1)
                cv2.putText(
                    debug_frame, f"{tag_id}",
                    (cx + 12, cy + 5), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, color, 2
                )

            # Draw quadrilateral if all 4 tags detected
            if len(screen.tag_centers) == 4:
                pts = np.array([
                    screen.tag_centers[tid] for tid in screen.region.tag_ids
                ], dtype=np.int32)
                cv2.polylines(debug_frame, [pts], True, color, 2)

            # Status text
            status = "OK" if screen.calibrated else "..."
            y_offset = 30 + idx * 25
            cv2.putText(
                debug_frame,
                f"{screen.region.name}: {status}",
                (10, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )

        return debug_frame


def run_demo(camera_index: int = 0, layout: str = "dual_horizontal"):
    """Run interactive multi-screen demo."""
    
    layouts = {
        "dual_horizontal": MultiScreenConfig.dual_horizontal,
        "dual_vertical": MultiScreenConfig.dual_vertical,
        "triple_horizontal": MultiScreenConfig.triple_horizontal,
    }
    
    if layout not in layouts:
        print(f"Unknown layout: {layout}")
        print(f"Available: {list(layouts.keys())}")
        return

    config = layouts[layout]()
    mapper = MultiScreenMapper(config)
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print("Error: Could not open camera")
        return

    print(f"Multi-Screen Registration Demo ({layout})")
    print("=" * 50)
    print("\nScreens:")
    for screen in config.screens:
        print(f"  {screen.name}: Tags {screen.tag_ids}")
        print(f"    Size: {screen.width}x{screen.height}")
        print(f"    Offset: ({screen.offset_x}, {screen.offset_y})")
    print("\nControls: 'q' = Quit, 'c' = Lock calibration")

    calibration_locked = False
    mouse_pos = None

    def mouse_callback(event, x, y, flags, param):
        nonlocal mouse_pos
        if event == cv2.EVENT_MOUSEMOVE:
            mouse_pos = (x, y)

    cv2.namedWindow("Multi-Screen Registration")
    cv2.setMouseCallback("Multi-Screen Registration", mouse_callback)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        mapper.detect_tags(frame)

        if not calibration_locked:
            mapper.compute_homographies()

        debug_frame = mapper.draw_debug(frame)

        # Show mouse mapping
        if mouse_pos:
            result = mapper.camera_to_screen(mouse_pos)
            if result:
                name, lx, ly, gx, gy = result
                cv2.circle(debug_frame, mouse_pos, 8, (0, 255, 0), -1)
                cv2.putText(
                    debug_frame,
                    f"{name} ({lx},{ly}) Global({gx},{gy})",
                    (mouse_pos[0] + 15, mouse_pos[1]),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )

        if calibration_locked:
            cv2.putText(
                debug_frame, "LOCKED",
                (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (255, 165, 0), 2
            )

        cv2.imshow("Multi-Screen Registration", debug_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            calibration_locked = not calibration_locked

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Multi-screen AprilTag registration (tag16h5)")
    parser.add_argument(
        "--layout",
        choices=["dual_horizontal", "dual_vertical", "triple_horizontal"],
        default="dual_horizontal",
        help="Screen layout preset",
    )
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    
    args = parser.parse_args()
    run_demo(camera_index=args.camera, layout=args.layout)
