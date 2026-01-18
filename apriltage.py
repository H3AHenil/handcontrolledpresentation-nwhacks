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

from contextlib import contextmanager
from typing import Generator, TypedDict

import cv2
import numpy as np
from numpy.typing import NDArray


# =============================================================================
# CONSTANTS
# =============================================================================

# Corner indices (counter-clockwise from bottom-left)
CORNER_BL, CORNER_BR, CORNER_TR, CORNER_TL = 0, 1, 2, 3

# BGR colors
COLOR_GREEN = (0, 255, 0)
COLOR_MAGENTA = (255, 0, 255)
COLOR_RED = (0, 0, 255)
COLOR_ORANGE = (0, 165, 255)
COLOR_YELLOW = (0, 200, 255)
COLOR_GRAY = (200, 200, 200)

# Drawing constants
FONT = cv2.FONT_HERSHEY_SIMPLEX
MARKER_RADIUS = 8
CURSOR_RADIUS = 6
LINE_THICKNESS = 2

# Normalized coordinate scale
SCALE_MAX = 1000

# Camera resolution
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

# Corner position indices within a screen's 4 tags: [TL, TR, BR, BL]
CORNER_POSITIONS = [0, 1, 2, 3]

# Which corner of each tag (by position) faces screen center
INNER_CORNER_BY_POSITION = {
    0: CORNER_BR,  # Top-left tag → use bottom-right corner
    1: CORNER_BL,  # Top-right tag → use bottom-left corner
    2: CORNER_TL,  # Bottom-right tag → use top-left corner
    3: CORNER_TR,  # Bottom-left tag → use top-right corner
}

# Adjacency pairs for drawing quadrilateral edges
EDGE_ADJACENCY = [(0, 1), (1, 2), (2, 3), (3, 0)]


def get_screen_tag_ids(screen_index: int) -> list[int]:
    """Get tag IDs for a given screen (0-3 for screen 0, 4-7 for screen 1, etc.)."""
    base = screen_index * 4
    return [base, base + 1, base + 2, base + 3]


def get_screen_index(tag_id: int) -> int:
    """Get screen index from tag ID (tags 0-3 → screen 0, 4-7 → screen 1, etc.)."""
    return tag_id // 4


def get_inner_corner(tag_id: int) -> int:
    """Get the inner corner index for a tag based on its position within the screen."""
    position = tag_id % 4
    return INNER_CORNER_BY_POSITION[position]


def detect_screens(tag_ids: list[int]) -> set[int]:
    """Detect which screens have visible tags."""
    return {get_screen_index(tid) for tid in tag_ids}


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

class MapperState(TypedDict):
    screen_index: int
    tag_ids: list[int]
    scale_max: int
    normalized_corners: NDArray[np.float32]
    homography: NDArray[np.float32] | None
    inverse_homography: NDArray[np.float32] | None
    camera_corners: NDArray[np.float32] | None
    detected_corners: dict[int, NDArray[np.float32]]
    num_tags_detected: int


class DetectionResult(TypedDict):
    tag_corners: dict[int, NDArray[np.float32]]
    raw_corners: tuple[NDArray[np.float32], ...]
    ids: NDArray[np.int32] | None


# =============================================================================
# MAPPER FUNCTIONS
# =============================================================================

def create_mapper(screen_index: int = 0, scale_max: int = SCALE_MAX) -> MapperState:
    """Create a new mapper state for a specific screen."""
    return {
        "screen_index": screen_index,
        "tag_ids": get_screen_tag_ids(screen_index),
        "scale_max": scale_max,
        "normalized_corners": np.array([
            [0, 0],
            [scale_max, 0],
            [scale_max, scale_max],
            [0, scale_max],
        ], dtype=np.float32),
        "homography": None,
        "inverse_homography": None,
        "camera_corners": None,
        "detected_corners": {},
        "num_tags_detected": 0,
    }


def _perspective_transform(
    x: float, y: float, matrix: NDArray[np.float32]
) -> tuple[float, float]:
    """Apply perspective transform to a single point."""
    pt = np.array([[[x, y]]], dtype=np.float32)
    transformed = cv2.perspectiveTransform(pt, matrix)
    return transformed[0, 0, 0], transformed[0, 0, 1]


def _extract_inner_corners(
    tag_corners: dict[int, NDArray[np.float32]], tag_ids: list[int]
) -> dict[int, NDArray[np.float32]]:
    """Extract inner corners from detected tag corners for specific tag IDs."""
    return {
        tag_id: tag_corners[tag_id][get_inner_corner(tag_id)]
        for tag_id in tag_ids
        if tag_id in tag_corners
    }


def update_mapper(
    state: MapperState, tag_corners: dict[int, NDArray[np.float32]]
) -> bool:
    """Update mapper homography from detected tag corners."""
    tag_ids = state["tag_ids"]
    state["detected_corners"] = _extract_inner_corners(tag_corners, tag_ids)
    state["num_tags_detected"] = len(state["detected_corners"])

    if state["num_tags_detected"] < 3:
        state["homography"] = None
        state["inverse_homography"] = None
        state["camera_corners"] = None
        return False

    if state["num_tags_detected"] == 4:
        src_points = [state["detected_corners"][tid] for tid in tag_ids]
        state["camera_corners"] = np.array(src_points, dtype=np.float32)
        state["homography"] = cv2.getPerspectiveTransform(
            state["camera_corners"], state["normalized_corners"]
        )
        state["inverse_homography"] = cv2.getPerspectiveTransform(
            state["normalized_corners"], state["camera_corners"]
        )
        return True

    # Affine transform with 3 tags (fallback)
    detected_ids = list(state["detected_corners"].keys())
    src_points = np.array(
        [state["detected_corners"][tid] for tid in detected_ids], dtype=np.float32
    )
    dst_points = np.array(
        [state["normalized_corners"][tag_ids.index(tid)] for tid in detected_ids],
        dtype=np.float32,
    )
    affine = cv2.getAffineTransform(src_points[:3], dst_points[:3])
    state["homography"] = np.vstack([affine, [0, 0, 1]]).astype(np.float32)
    state["inverse_homography"] = np.linalg.inv(state["homography"]).astype(np.float32)
    state["camera_corners"] = None
    return True


def camera_to_normalized(
    state: MapperState, x: float, y: float
) -> tuple[int, int] | None:
    """Map camera pixel to normalized coordinates (0 to scale_max)."""
    if state["homography"] is None:
        return None
    tx, ty = _perspective_transform(x, y, state["homography"])
    return int(round(tx)), int(round(ty))


def camera_to_ratio(
    state: MapperState, x: float, y: float
) -> tuple[float, float] | None:
    """Map camera pixel to ratio coordinates (0.0 to 1.0)."""
    if state["homography"] is None:
        return None
    tx, ty = _perspective_transform(x, y, state["homography"])
    return tx / state["scale_max"], ty / state["scale_max"]


def normalized_to_camera(
    state: MapperState, nx: float, ny: float
) -> tuple[int, int] | None:
    """Map normalized coordinates to camera pixel."""
    if state["inverse_homography"] is None:
        return None
    tx, ty = _perspective_transform(nx, ny, state["inverse_homography"])
    return int(round(tx)), int(round(ty))


def is_in_bounds(state: MapperState, nx: int, ny: int) -> bool:
    """Check if normalized coordinates are within bounds."""
    return 0 <= nx <= state["scale_max"] and 0 <= ny <= state["scale_max"]


def is_calibrated(state: MapperState) -> bool:
    """Check if mapper is calibrated."""
    return state["homography"] is not None


def get_screen_corners(state: MapperState) -> dict[str, tuple[int, int]] | None:
    """
    Get camera pixel coordinates of screen corners.

    Returns:
        Dict with keys 'tl', 'tr', 'br', 'bl' mapping to (x, y) pixel coordinates,
        or None if not all 4 tags are detected.
    """
    if state["num_tags_detected"] != 4 or state["camera_corners"] is None:
        return None

    corners = state["camera_corners"]
    return {
        "tl": (int(corners[0][0]), int(corners[0][1])),
        "tr": (int(corners[1][0]), int(corners[1][1])),
        "br": (int(corners[2][0]), int(corners[2][1])),
        "bl": (int(corners[3][0]), int(corners[3][1])),
    }


def get_all_screen_corners(
    states: dict[int, MapperState]
) -> dict[int, dict[str, tuple[int, int]]]:
    """
    Get camera pixel coordinates for all calibrated screens.

    Returns:
        Dict mapping screen_index -> corner dict {'tl', 'tr', 'br', 'bl': (x, y)}
        Only includes screens with all 4 tags detected.
    """
    return {
        screen_idx: corners
        for screen_idx, state in states.items()
        if (corners := get_screen_corners(state)) is not None
    }


# =============================================================================
# CAMERA FUNCTIONS
# =============================================================================

@contextmanager
def open_camera(
    index: int = 0, width: int = CAMERA_WIDTH, height: int = CAMERA_HEIGHT
) -> Generator[cv2.VideoCapture, None, None]:
    """Context manager for camera resource."""
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open camera at index {index}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    try:
        yield cap
    finally:
        cap.release()


def read_frame(cap: cv2.VideoCapture) -> NDArray[np.uint8] | None:
    """Read a frame from the camera."""
    ret, frame = cap.read()
    return frame if ret else None


# =============================================================================
# APRILTAG DETECTION
# =============================================================================

def create_detector() -> cv2.aruco.ArucoDetector:
    """Create and configure the AprilTag detector."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_16h5)
    parameters = cv2.aruco.DetectorParameters()
    parameters.minMarkerPerimeterRate = 0.03
    parameters.errorCorrectionRate = 0.1
    return cv2.aruco.ArucoDetector(aruco_dict, parameters)


def detect_tags(
    detector: cv2.aruco.ArucoDetector, frame: NDArray[np.uint8]
) -> DetectionResult:
    """Detect all AprilTags in the frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)

    tag_corners = {
        int(marker_id): corners[i].squeeze()
        for i, marker_id in enumerate(ids.flatten())
    } if ids is not None else {}

    return {"tag_corners": tag_corners, "raw_corners": corners, "ids": ids}


# =============================================================================
# VISUALIZATION FUNCTIONS
# =============================================================================

def draw_detected_markers(
    frame: NDArray[np.uint8],
    corners: tuple[NDArray[np.float32], ...],
    ids: NDArray[np.int32] | None,
) -> None:
    """Draw the detected AprilTag markers."""
    if ids is not None:
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)


def draw_inner_corners(
    frame: NDArray[np.uint8], tag_corners: dict[int, NDArray[np.float32]]
) -> None:
    """Draw circles on inner corners used for calibration."""
    for tag_id, corners in tag_corners.items():
        point = tuple(corners[get_inner_corner(tag_id)].astype(int))
        cv2.circle(frame, point, MARKER_RADIUS, COLOR_GREEN, -1)


def draw_screen_quadrilateral(frame: NDArray[np.uint8], state: MapperState) -> None:
    """Draw shape connecting detected calibration points."""
    if state["num_tags_detected"] == 0:
        return

    tag_ids = state["tag_ids"]
    if state["num_tags_detected"] == 4:
        pts = np.array(
            [state["detected_corners"][tid] for tid in tag_ids], dtype=np.int32
        )
        cv2.polylines(frame, [pts], True, COLOR_MAGENTA, LINE_THICKNESS)
    elif state["num_tags_detected"] >= 2:
        for pos1, pos2 in EDGE_ADJACENCY:
            tid1, tid2 = tag_ids[pos1], tag_ids[pos2]
            if tid1 in state["detected_corners"] and tid2 in state["detected_corners"]:
                pt1 = tuple(state["detected_corners"][tid1].astype(int))
                pt2 = tuple(state["detected_corners"][tid2].astype(int))
                cv2.line(frame, pt1, pt2, COLOR_MAGENTA, LINE_THICKNESS)


def draw_calibration_status(
    frame: NDArray[np.uint8],
    state: MapperState,
    y_offset: int = 30,
) -> None:
    """Draw calibration status text for a single screen."""
    screen_idx = state["screen_index"]
    tag_ids = state["tag_ids"]
    n = state["num_tags_detected"]
    detected = [tid for tid in tag_ids if tid in state["detected_corners"]]

    prefix = f"Screen {screen_idx}: "
    if n == 4:
        cv2.putText(frame, f"{prefix}CALIBRATED (4 tags)", (10, y_offset), FONT, 0.7, COLOR_GREEN, 2)
    elif n == 3:
        cv2.putText(frame, f"{prefix}CALIBRATED (3 tags)", (10, y_offset), FONT, 0.7, COLOR_YELLOW, 2)
    else:
        cv2.putText(frame, f"{prefix}Detected {detected} (need 3+)", (10, y_offset), FONT, 0.6, COLOR_RED, 2)


def draw_mouse_mapping(
    frame: NDArray[np.uint8],
    state: MapperState,
    mouse_pos: tuple[int, int] | None,
) -> None:
    """Draw mouse position and mapped normalized coordinates."""
    if mouse_pos is None or not is_calibrated(state):
        return

    mx, my = mouse_pos
    norm_pt = camera_to_normalized(state, mx, my)
    ratio_pt = camera_to_ratio(state, mx, my)

    if norm_pt and ratio_pt:
        nx, ny = norm_pt
        rx, ry = ratio_pt
        color = COLOR_GREEN if is_in_bounds(state, nx, ny) else COLOR_ORANGE

        cv2.circle(frame, (mx, my), CURSOR_RADIUS, color, -1)
        cv2.putText(frame, f"Norm: ({nx}, {ny})", (mx + 10, my - 10), FONT, 0.5, color, 2)
        cv2.putText(frame, f"Ratio: ({rx:.3f}, {ry:.3f})", (mx + 10, my + 10), FONT, 0.4, color, 1)


def draw_info_bar(frame: NDArray[np.uint8], num_screens: int, scale_max: int = SCALE_MAX) -> None:
    """Draw information bar at the bottom."""
    h, w = frame.shape[:2]
    info = f"Camera: {w}x{h} | Screens: {num_screens} | Scale: 0-{scale_max}"
    cv2.putText(frame, info, (10, h - 10), FONT, 0.5, COLOR_GRAY, 1)


def draw_all(
    frame: NDArray[np.uint8],
    detection: DetectionResult,
    states: list[MapperState],
    mouse_pos: tuple[int, int] | None,
) -> None:
    """Draw all visualizations on the frame for multiple screens."""
    draw_detected_markers(frame, detection["raw_corners"], detection["ids"])
    draw_inner_corners(frame, detection["tag_corners"])

    for i, state in enumerate(states):
        draw_screen_quadrilateral(frame, state)
        draw_calibration_status(frame, state, y_offset=30 + i * 25)
        draw_mouse_mapping(frame, state, mouse_pos)

    draw_info_bar(frame, len(states))


# =============================================================================
# APPLICATION
# =============================================================================

def get_instructions() -> str:
    """Generate instructions for auto-detected multi-screen setup."""
    return """
==================================================
AprilTag Multi-Screen Registration (tag16h5)
==================================================

Screens auto-detected from visible tags:
  Screen 0: IDs 0-3   (0=TL, 1=TR, 2=BR, 3=BL)
  Screen 1: IDs 4-7   (4=TL, 5=TR, 6=BR, 7=BL)
  Screen N: IDs N*4 to N*4+3

Controls:
  'q' - Quit
  Mouse - Show mapped coordinates
"""


def create_mouse_tracker():
    """Create mouse tracker using closure."""
    pos = [None]

    def callback(event: int, x: int, y: int, flags: int, param) -> None:
        if event == cv2.EVENT_MOUSEMOVE:
            pos[0] = (x, y)

    def get_position() -> tuple[int, int] | None:
        return pos[0]

    return callback, get_position


def process_frame(
    frame: NDArray[np.uint8],
    detector: cv2.aruco.ArucoDetector,
    states: dict[int, MapperState],
    mouse_pos: tuple[int, int] | None,
) -> None:
    """Process a single frame: detect, update all mappers, draw."""
    detection = detect_tags(detector, frame)

    # Auto-detect screens from visible tags
    visible_screens = detect_screens(list(detection["tag_corners"].keys()))

    # Create mappers for newly detected screens
    for screen_idx in visible_screens:
        if screen_idx not in states:
            states[screen_idx] = create_mapper(screen_index=screen_idx)

    # Update all known mappers
    for state in states.values():
        update_mapper(state, detection["tag_corners"])

    # Draw (sorted by screen index)
    sorted_states = [states[i] for i in sorted(states.keys())]
    draw_all(frame, detection, sorted_states, mouse_pos)


def run_demo(camera_index: int = 0) -> None:
    """Run the interactive demo with auto-detected screens."""
    print(get_instructions())

    detector = create_detector()
    states: dict[int, MapperState] = {}  # Auto-populated as screens are detected
    mouse_callback, get_mouse_pos = create_mouse_tracker()

    window_name = "AprilTag Multi-Screen Registration"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, mouse_callback)

    try:
        with open_camera(camera_index) as cap:
            while True:
                frame = read_frame(cap)
                if frame is None:
                    break

                process_frame(frame, detector, states, get_mouse_pos())
                cv2.imshow(window_name, frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except RuntimeError as e:
        print(f"Error: {e}")
    finally:
        cv2.destroyAllWindows()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AprilTag Multi-Screen Registration")
    parser.add_argument("-c", "--camera", type=int, default=0, help="Camera index")
    args = parser.parse_args()

    run_demo(camera_index=args.camera)
