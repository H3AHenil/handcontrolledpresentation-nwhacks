"""
Finger-to-Screen Coordinate Tracker

Integrates AprilTag screen detection with MediaPipe hand tracking.
Maps finger position to screen coordinates using perspective-correct homography.
"""

import sys
from pathlib import Path

from server.receiver import frames_from_udp, create_udp_socket, PORT

# Add parent directory to path for apriltage import
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import mediapipe as mp
import numpy as np
from numpy.typing import NDArray

from apriltage import (
    create_detector,
    create_mapper,
    detect_tags,
    detect_screens,
    update_mapper,
    camera_to_ratio,
    is_calibrated,
    get_screen_corners,
    MapperState,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    COLOR_GREEN,
    COLOR_MAGENTA,
    COLOR_RED,
    COLOR_YELLOW,
    COLOR_GRAY,
    FONT,
    LINE_THICKNESS,
)


# =============================================================================
# FINGER TRACKING
# =============================================================================

def create_hand_tracker():
    """Create MediaPipe hand tracker."""
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7,
    )
    return hands, mp_hands, mp.solutions.drawing_utils


def get_index_finger_tip(
    hands, frame: NDArray[np.uint8]
) -> tuple[int, int] | None:
    """Get index finger tip position from frame."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    if not results.multi_hand_landmarks:
        return None

    hand = results.multi_hand_landmarks[0]
    lm = hand.landmark[8]  # Index finger tip

    h, w = frame.shape[:2]
    return int(lm.x * w), int(lm.y * h)


def draw_hand_landmarks(
    frame: NDArray[np.uint8], hands, mp_hands, mp_draw
) -> None:
    """Draw hand landmarks on frame."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    if results.multi_hand_landmarks:
        for hand in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)


# =============================================================================
# COORDINATE MAPPING
# =============================================================================

def finger_to_screen_ratio(
    state: MapperState, finger_x: int, finger_y: int
) -> tuple[float, float] | None:
    """
    Map finger camera position to screen ratio coordinates (0.0 to 1.0).

    Uses perspective-correct homography transformation.

    Returns:
        (rel_x, rel_y) in [0.0, 1.0] range, or None if screen not calibrated
    """
    return camera_to_ratio(state, finger_x, finger_y)


def is_finger_in_screen(
    state: MapperState, finger_x: int, finger_y: int
) -> bool:
    """Check if finger position is within the screen boundary."""
    result = camera_to_ratio(state, finger_x, finger_y)
    if result is None:
        return False
    rx, ry = result
    return 0 <= rx <= 1 and 0 <= ry <= 1


def find_finger_screen(
    states: dict[int, MapperState], finger_x: int, finger_y: int
) -> tuple[int, tuple[float, float]] | None:
    """
    Find which screen the finger is pointing at.

    Returns:
        (screen_index, (rel_x, rel_y)) or None if finger not on any screen
    """
    for screen_idx, state in states.items():
        if not is_calibrated(state):
            continue
        result = camera_to_ratio(state, finger_x, finger_y)
        if result:
            rx, ry = result
            if 0 <= rx <= 1 and 0 <= ry <= 1:
                return screen_idx, (rx, ry)
    return None


# =============================================================================
# VISUALIZATION
# =============================================================================

def draw_screen_boundary(frame: NDArray[np.uint8], state: MapperState) -> None:
    """Draw the screen boundary quadrilateral."""
    corners = get_screen_corners(state)
    if corners is None:
        return

    pts = np.array([
        corners["tl"], corners["tr"], corners["br"], corners["bl"]
    ], dtype=np.int32)
    cv2.polylines(frame, [pts], True, COLOR_MAGENTA, LINE_THICKNESS)


def draw_finger_info(
    frame: NDArray[np.uint8],
    finger_pos: tuple[int, int] | None,
    screen_result: tuple[int, tuple[float, float]] | None,
) -> None:
    """Draw finger position and screen mapping info."""
    if finger_pos is None:
        cv2.putText(frame, "No hand detected", (10, 30), FONT, 0.7, COLOR_GRAY, 2)
        return

    fx, fy = finger_pos
    cv2.circle(frame, (fx, fy), 12, COLOR_GREEN, -1)
    cv2.circle(frame, (fx, fy), 14, (0, 0, 0), 2)

    if screen_result:
        screen_idx, (rx, ry) = screen_result
        color = COLOR_GREEN
        text = f"Screen {screen_idx}: ({rx:.3f}, {ry:.3f})"
    else:
        color = COLOR_RED
        text = "Outside screen bounds"

    cv2.putText(frame, text, (10, 30), FONT, 0.8, color, 2)
    cv2.putText(frame, f"Finger: ({fx}, {fy})", (10, 60), FONT, 0.6, COLOR_GRAY, 2)


def draw_calibration_status(
    frame: NDArray[np.uint8], states: dict[int, MapperState], y_start: int = 90
) -> None:
    """Draw calibration status for all screens."""
    if not states:
        cv2.putText(frame, "No AprilTags detected", (10, y_start), FONT, 0.6, COLOR_RED, 2)
        return

    for i, (screen_idx, state) in enumerate(sorted(states.items())):
        y = y_start + i * 25
        n = state["num_tags_detected"]
        if n == 4:
            color = COLOR_GREEN
            status = "READY"
        elif n >= 3:
            color = COLOR_YELLOW
            status = f"{n}/4 tags"
        else:
            color = COLOR_RED
            status = f"{n}/4 tags"
        cv2.putText(frame, f"Screen {screen_idx}: {status}", (10, y), FONT, 0.5, color, 2)


# =============================================================================
# MAIN APPLICATION
# =============================================================================

def run_finger_tracker(camera_index: int = 0) -> None:
    """Run the finger-to-screen coordinate tracker."""
    print("""
==================================================
Finger-to-Screen Coordinate Tracker
==================================================

Place AprilTags at screen corners:
  Screen 0: IDs 0-3   (0=TL, 1=TR, 2=BR, 3=BL)
  Screen 1: IDs 4-7   (4=TL, 5=TR, 6=BR, 7=BL)

Point your index finger at the screen to see coordinates.

Controls:
  'q' or ESC - Quit
""")

    # Initialize detectors
    tag_detector = create_detector()
    hands, mp_hands, mp_draw = create_hand_tracker()
    states: dict[int, MapperState] = {}

    # Open camera
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Error: Cannot open camera {camera_index}")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    window_name = "Finger Screen Tracker"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    sock = create_udp_socket(PORT)
    stream_gen = frames_from_udp(
        sock,
        wide_angle_crop=False,
        original_hfov_deg=160.0
    )
    try:
        for frame, latency in stream_gen:

            frame = cv2.flip(frame, -1)
            # Detect AprilTags and update screen mappers
            detection = detect_tags(tag_detector, frame)
            visible_screens = detect_screens(list(detection["tag_corners"].keys()))

            for screen_idx in visible_screens:
                if screen_idx not in states:
                    states[screen_idx] = create_mapper(screen_index=screen_idx)

            for state in states.values():
                update_mapper(state, detection["tag_corners"])

            # Get finger position
            finger_pos = get_index_finger_tip(hands, frame)

            # Find which screen finger is on
            screen_result = None
            if finger_pos:
                screen_result = find_finger_screen(states, *finger_pos)

            # Draw visualizations
            draw_hand_landmarks(frame, hands, mp_hands, mp_draw)
            for state in states.values():
                draw_screen_boundary(frame, state)
            draw_finger_info(frame, finger_pos, screen_result)
            draw_calibration_status(frame, states)

            cv2.imshow(window_name, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):  # 'q' or ESC
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        hands.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Finger-to-Screen Coordinate Tracker")
    parser.add_argument("-c", "--camera", type=int, default=0, help="Camera index")
    args = parser.parse_args()

    run_finger_tracker(camera_index=args.camera)
