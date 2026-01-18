"""
AprilTag Screen Registration with Homography Mapping (tag16h5)

Screen Registration:
- Detects 4 AprilTags (IDs 0-3) at screen corners
- Tags act as anchors for position/orientation tracking

Inverse Perspective Mapping:
- Camera sees screen as trapezoid (due to viewing angle)
- Homography matrix "un-warps" trapezoid → rectangle
- Maps any camera pixel to actual screen coordinates
"""

import cv2
import numpy as np

# =============================================================================
# CONFIGURATION
# =============================================================================

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

# Tag IDs for each corner: [top-left, top-right, bottom-right, bottom-left]
CORNER_TAG_IDS = [0, 1, 2, 3]

# AprilTag corner indices (counter-clockwise from bottom-left)
CORNER_BL, CORNER_BR, CORNER_TR, CORNER_TL = 0, 1, 2, 3

# Which corner of each tag faces the screen center (inner corner)
INNER_CORNER = {
    0: CORNER_BR,  # Top-left tag → use bottom-right corner
    1: CORNER_BL,  # Top-right tag → use bottom-left corner
    2: CORNER_TL,  # Bottom-right tag → use top-left corner
    3: CORNER_TR,  # Bottom-left tag → use top-right corner
}


# =============================================================================
# SCREEN MAPPER CLASS
# =============================================================================

class ScreenMapper:
    """Maps camera coordinates to screen coordinates using AprilTag homography."""

    def __init__(self, screen_width: int = SCREEN_WIDTH, screen_height: int = SCREEN_HEIGHT):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Destination points (screen corners)
        self.screen_corners = np.array([
            [0, 0],
            [screen_width - 1, 0],
            [screen_width - 1, screen_height - 1],
            [0, screen_height - 1],
        ], dtype=np.float32)

        self.homography = None
        self.inverse_homography = None
        self.camera_corners = None

    def update(self, tag_corners: dict[int, np.ndarray]) -> bool:
        """Update homography from detected tag corners."""
        if not all(tid in tag_corners for tid in CORNER_TAG_IDS):
            return False

        src_points = []
        for tag_id in CORNER_TAG_IDS:
            corners = tag_corners[tag_id]
            inner_idx = INNER_CORNER[tag_id]
            src_points.append(corners[inner_idx])

        self.camera_corners = np.array(src_points, dtype=np.float32)

        self.homography = cv2.getPerspectiveTransform(
            self.camera_corners, self.screen_corners
        )
        self.inverse_homography = cv2.getPerspectiveTransform(
            self.screen_corners, self.camera_corners
        )
        return True

    def camera_to_screen(self, x: float, y: float) -> tuple[int, int] | None:
        """Map camera pixel to screen pixel."""
        if self.homography is None:
            return None

        pt = np.array([[[x, y]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.homography)
        return (int(round(transformed[0, 0, 0])), int(round(transformed[0, 0, 1])))

    def screen_to_camera(self, x: float, y: float) -> tuple[int, int] | None:
        """Map screen pixel to camera pixel."""
        if self.inverse_homography is None:
            return None

        pt = np.array([[[x, y]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.inverse_homography)
        return (int(round(transformed[0, 0, 0])), int(round(transformed[0, 0, 1])))

    def is_on_screen(self, sx: int, sy: int) -> bool:
        """Check if screen coordinates are within bounds."""
        return 0 <= sx < self.screen_width and 0 <= sy < self.screen_height

    @property
    def is_calibrated(self) -> bool:
        return self.homography is not None


# =============================================================================
# CAMERA FUNCTIONS
# =============================================================================

def setup_camera(index: int = 0, width: int = CAMERA_WIDTH, height: int = CAMERA_HEIGHT) -> cv2.VideoCapture:
    """Initialize and configure the camera."""
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap


def read_frame(cap: cv2.VideoCapture) -> np.ndarray | None:
    """Read a frame from the camera."""
    ret, frame = cap.read()
    return frame if ret else None


# =============================================================================
# APRILTAG DETECTION FUNCTIONS
# =============================================================================

def create_detector() -> cv2.aruco.ArucoDetector:
    """Create and configure the AprilTag detector."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_16h5)
    parameters = cv2.aruco.DetectorParameters()
    parameters.minMarkerPerimeterRate = 0.03
    parameters.errorCorrectionRate = 0.1
    return cv2.aruco.ArucoDetector(aruco_dict, parameters)


def detect_tags(detector: cv2.aruco.ArucoDetector, frame: np.ndarray) -> tuple[dict[int, np.ndarray], list, np.ndarray | None]:
    """
    Detect AprilTags in the frame.

    Returns:
        tag_corners: Dict mapping tag_id -> 4 corner points
        all_corners: Raw corners from detector (for drawing)
        ids: Detected marker IDs
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)

    tag_corners = {}
    if ids is not None:
        for i, marker_id in enumerate(ids.flatten()):
            if marker_id in CORNER_TAG_IDS:
                tag_corners[marker_id] = corners[i].squeeze()

    return tag_corners, corners, ids


# =============================================================================
# VISUALIZATION FUNCTIONS
# =============================================================================

def draw_detected_markers(frame: np.ndarray, corners: list, ids: np.ndarray | None) -> None:
    """Draw the detected AprilTag markers."""
    if ids is not None:
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)


def draw_inner_corners(frame: np.ndarray, tag_corners: dict[int, np.ndarray]) -> None:
    """Draw green circles on the inner corners used for calibration."""
    for tag_id, crns in tag_corners.items():
        inner_idx = INNER_CORNER[tag_id]
        ix, iy = int(crns[inner_idx][0]), int(crns[inner_idx][1])
        cv2.circle(frame, (ix, iy), 8, (0, 255, 0), -1)


def draw_screen_quadrilateral(frame: np.ndarray, mapper: ScreenMapper) -> None:
    """Draw magenta quadrilateral connecting the calibration points."""
    if mapper.camera_corners is not None:
        pts = mapper.camera_corners.astype(np.int32)
        cv2.polylines(frame, [pts], True, (255, 0, 255), 2)


def draw_calibration_status(frame: np.ndarray, mapper: ScreenMapper, tag_corners: dict) -> None:
    """Draw calibration status text."""
    if mapper.is_calibrated:
        cv2.putText(frame, "CALIBRATED", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    else:
        detected = list(tag_corners.keys())
        cv2.putText(frame, f"Detected: {detected} (need 0,1,2,3)", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)


def draw_mouse_mapping(frame: np.ndarray, mapper: ScreenMapper, mouse_pos: tuple[int, int] | None) -> None:
    """Draw mouse position and its mapped screen coordinates."""
    if mouse_pos is None or not mapper.is_calibrated:
        return

    mx, my = mouse_pos
    screen_pt = mapper.camera_to_screen(mx, my)
    if screen_pt:
        sx, sy = screen_pt
        on_screen = mapper.is_on_screen(sx, sy)
        color = (0, 255, 0) if on_screen else (0, 165, 255)

        cv2.circle(frame, (mx, my), 6, color, -1)
        cv2.putText(frame, f"Screen: ({sx}, {sy})",
                    (mx + 10, my - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def draw_info_bar(frame: np.ndarray, mapper: ScreenMapper) -> None:
    """Draw information bar at the bottom of the frame."""
    h, w = frame.shape[:2]
    info = f"Camera: {w}x{h} | Screen: {mapper.screen_width}x{mapper.screen_height}"
    cv2.putText(frame, info, (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)


def draw_all(
    frame: np.ndarray,
    corners: list,
    ids: np.ndarray | None,
    tag_corners: dict[int, np.ndarray],
    mapper: ScreenMapper,
    mouse_pos: tuple[int, int] | None,
) -> None:
    """Draw all visualizations on the frame."""
    draw_detected_markers(frame, corners, ids)
    draw_inner_corners(frame, tag_corners)
    draw_screen_quadrilateral(frame, mapper)
    draw_calibration_status(frame, mapper, tag_corners)
    draw_mouse_mapping(frame, mapper, mouse_pos)
    draw_info_bar(frame, mapper)


# =============================================================================
# MAIN LOOP
# =============================================================================

def print_instructions() -> None:
    """Print usage instructions to console."""
    print("=" * 50)
    print("AprilTag Screen Registration (tag16h5)")
    print("=" * 50)
    print("\nPlace tags at screen corners:")
    print("  ID 0: Top-left     ID 1: Top-right")
    print("  ID 3: Bottom-left  ID 2: Bottom-right")
    print("\nControls:")
    print("  'q' - Quit")
    print("  Mouse - Show mapped screen coordinates")
    print()


def create_mouse_callback():
    """Create a mouse callback and return (callback_fn, position_getter)."""
    mouse_pos = [None]

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_MOUSEMOVE:
            mouse_pos[0] = (x, y)

    def get_pos():
        return mouse_pos[0]

    return on_mouse, get_pos


def process_frame(
    frame: np.ndarray,
    detector: cv2.aruco.ArucoDetector,
    mapper: ScreenMapper,
    mouse_pos: tuple[int, int] | None,
) -> None:
    """Process a single frame: detect, update, draw."""
    # Detect tags
    tag_corners, corners, ids = detect_tags(detector, frame)

    # Update homography
    mapper.update(tag_corners)

    # Draw visualizations
    draw_all(frame, corners, ids, tag_corners, mapper, mouse_pos)


def run_demo(camera_index: int = 0) -> None:
    """Run the interactive demo."""
    print_instructions()

    # Setup
    cap = setup_camera(camera_index)
    detector = create_detector()
    mapper = ScreenMapper()

    # Window and mouse
    window_name = "AprilTag Screen Registration"
    cv2.namedWindow(window_name)
    mouse_callback, get_mouse_pos = create_mouse_callback()
    cv2.setMouseCallback(window_name, mouse_callback)

    # Main loop
    while True:
        frame = read_frame(cap)
        if frame is None:
            break

        process_frame(frame, detector, mapper, get_mouse_pos())
        cv2.imshow(window_name, frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    run_demo()
