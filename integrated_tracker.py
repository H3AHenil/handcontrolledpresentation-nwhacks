"""
Integrated Hand Gesture and Screen Tracker.

Combines:
- Gesture detection (Pointer, Pinch, TwoFingerSwipe, Stretch, HandRot, Clap)
- AprilTag-based screen coordinate mapping
- UDP backend service for remote control
"""

import cv2
import time
from dataclasses import dataclass
from typing import Literal

from apriltage import CAMERA_WIDTH, CAMERA_HEIGHT
from server.receiver import LowLatencyReceiver, PORT
from src.hand_gestures import (
    VIEW_MODE, MAX_NUM_HANDS,
    extract_features,
    get_handedness_label,
    HandState,
    DetectedHand,
    is_pointer,
    is_two_finger_pose,
    update_pinch,
    update_thumbrot,
    update_two_finger_swipe,
    ClapDetector,
    StretchDetector,
)
from src.hand_gestures.config import DISPLAY_FLIP, PROCESS_FLIP, STRETCH_REQUIRE_POINTERS
from src.hand_tracks import MultiScreenMapper, TrackerDisplay, ScreenResult
from backend_service import GestureBackendService

import mediapipe as mp

mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands


INSTRUCTIONS = """
==================================================
Integrated Hand Gesture + Screen Tracker
==================================================

Gestures: Pointer, Pinch, TwoFingerSwipe, Stretch, HandRot, Clap

Place AprilTags at screen corners:
  Screen 0: IDs 0-3   (0=TL, 1=TR, 2=BR, 3=BL)
  Screen 1: IDs 4-7   (4=TL, 5=TR, 6=BR, 7=BL)

Controls:
  'q' or ESC - Quit
"""


def _get_display_label(d: DetectedHand, state: HandState, now: float) -> str:
    """Get display label for detected hand."""
    if d.thumbrot:
        return "HandRot"
    if now < state.latched_until:
        return state.latched_label
    if d.pinch:
        return "Pinch (held)"
    if d.two_finger:
        return "TwoFinger (ready)"
    if d.pointer:
        return "Pointer"
    return "Neutral"


def _draw_overlay(frame, overlay: list[str]):
    """Draw text overlay on frame."""
    if not overlay:
        return
    x0, y0, line_h = 12, 22, 22
    max_chars = max(len(s) for s in overlay)
    box_w = min(16 + max_chars * 9, frame.shape[1] - 24)
    box_h = 12 + line_h * len(overlay)

    cv2.rectangle(frame, (8, 8), (8 + box_w, 8 + box_h), (0, 0, 0), -1)
    for i, s in enumerate(overlay):
        cv2.putText(frame, s, (x0, y0 + i * line_h),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)


@dataclass
class FrameGestureData:
    """Aggregated gesture data for a single frame."""
    detected: list[DetectedHand]
    overlay: list[str]
    clap_active: bool
    stretch_active: bool
    stretch_cumulative: float
    swipe_detected: bool
    swipe_direction: Literal["left", "right"] | None


def process_hands(
    frame,
    results,
    states: dict[str, HandState],
    clap_detector: ClapDetector,
    stretch_detector: StretchDetector,
    now: float,
) -> FrameGestureData:
    """
    Process hand detection results and return detected hands + gesture data.
    
    Returns:
        FrameGestureData with all gesture information for the frame
    """
    h, w = frame.shape[:2]
    detected: list[DetectedHand] = []
    overlay = [f"Mode: {VIEW_MODE.value}"]

    used_labels = set()
    if results.multi_hand_landmarks:
        for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
            # Determine handedness label
            lbl = "Unknown"
            if results.multi_handedness and i < len(results.multi_handedness):
                lbl = get_handedness_label(results.multi_handedness[i])

            if lbl in used_labels:
                lbl = "Left" if "Left" not in used_labels else (
                    "Right" if "Right" not in used_labels else "Unknown"
                )
            used_labels.add(lbl)

            # Extract landmarks
            px = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]
            n3 = [(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark]
            feats = extract_features(px, n3)

            state = states[lbl]
            clap_detector.update_last_seen(lbl, feats, now)

            # Detect poses
            pointer = is_pointer(feats)
            two_finger = is_two_finger_pose(feats)

            # Update thumbrot detection
            thumbrot, yaw, pitch, roll = update_thumbrot(state, feats, now, pointer)

            # Update pinch detection (suppressed during thumbrot or two-finger)
            pinch = update_pinch(state, feats, now, suppressed=(thumbrot or two_finger))

            if pinch:
                pointer = False

            # Draw hand
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            for lm in hand_landmarks.landmark:
                cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 5, (0, 255, 0), -1)

            if pointer or pinch:
                cv2.circle(frame, feats.index_tip_px, 10, (0, 255, 0), -1)

            detected.append(DetectedHand(
                label=lbl, feats=feats, pointer=pointer,
                two_finger=two_finger, pinch=pinch, thumbrot=thumbrot,
                yaw=yaw, pitch=pitch, roll=roll,
            ))

    # Two-hand gestures
    clap_active, clap_intent = clap_detector.update(detected, now)
    if clap_active:
        overlay.append("GLOBAL: Clap")

    # Two-finger swipe detection
    swipe_detected = False
    swipe_direction: Literal["left", "right"] | None = None
    for d in detected:
        state = states[d.label]
        suppressed = clap_active or clap_intent or d.thumbrot or d.pinch
        detected_swipe, direction = update_two_finger_swipe(state, d.feats, now, d.two_finger, suppressed)
        if detected_swipe and direction:
            swipe_detected = True
            swipe_direction = direction
            overlay.append(f"SWIPE: {direction}")

    # Stretch detection
    stretch_active, stretch_delta, stretch_speed, stretch_cumulative = (
        stretch_detector.update(detected, now, STRETCH_REQUIRE_POINTERS)
    )
    if stretch_active and len(detected) >= 2:
        p0, p1 = detected[0].feats.index_tip_px, detected[1].feats.index_tip_px
        cv2.line(frame, p0, p1, (255, 255, 255), 2)
        overlay.append(f"Stretch Δ: {stretch_delta:+.1f}px  ({stretch_speed:+.0f}px/s)")
        overlay.append(f"Stretch Σ: {stretch_cumulative:+.1f}px")

    # Build overlay text for each hand
    if detected:
        for d in detected:
            state = states[d.label]
            disp = _get_display_label(d, state, now)

            if d.thumbrot and d.yaw is not None:
                overlay.append(f"{d.label}: {disp}  yaw={d.yaw:+.1f}  pitch={d.pitch:+.1f}  roll={d.roll:+.1f}")
            else:
                overlay.append(f"{d.label}: {disp}")
    else:
        overlay.append("No hands detected")

    return FrameGestureData(
        detected=detected,
        overlay=overlay,
        clap_active=clap_active,
        stretch_active=stretch_active,
        stretch_cumulative=stretch_cumulative,
        swipe_detected=swipe_detected,
        swipe_direction=swipe_direction,
    )


def get_active_finger(detected: list[DetectedHand]) -> tuple[int, int] | None:
    """Get the index finger position from the first hand in pointer or pinch mode."""
    # Priority: pointer mode first, then pinch mode
    for d in detected:
        if d.pointer:
            return d.feats.index_tip_px
    for d in detected:
        if d.pinch:
            return d.feats.index_tip_px
    return None


def run_integrated_tracker(
    camera_index: int = 0,
    enable_udp: bool = True,
    udp_ip: str = "127.0.0.1",
    udp_gesture_port: int = 9090,
    udp_legacy_port: int = 8080,
    broadcast: bool = False,
) -> None:
    """
    Run the integrated hand gesture and screen tracker.
    
    Args:
        camera_index: Camera device index
        enable_udp: Whether to enable UDP backend service
        udp_ip: Target IP for UDP commands
        udp_gesture_port: Port for gesture JSON protocol
        udp_legacy_port: Port for legacy text protocol
        broadcast: Whether to use UDP broadcast mode
    """
    print(INSTRUCTIONS)
    if enable_udp:
        print(f"UDP Backend: Enabled (target={udp_ip}:{udp_gesture_port})")
    else:
        print("UDP Backend: Disabled")

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Error: Cannot open camera {camera_index}")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    # Gesture detection state
    states = {k: HandState(label=k) for k in ["Left", "Right", "Unknown"]}
    clap_detector = ClapDetector()
    stretch_detector = StretchDetector()

    # Screen mapping
    mapper = MultiScreenMapper()
    receiver = LowLatencyReceiver(PORT, wide_angle_crop=False)

    # Backend service for UDP
    with GestureBackendService(
        gesture_port=udp_gesture_port,
        legacy_port=udp_legacy_port,
        target_ip=udp_ip,
        broadcast=broadcast,
        enabled=enable_udp,
    ) as backend, mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=MAX_NUM_HANDS,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as hands, TrackerDisplay() as display:

        while True:

            frame, latency = receiver.get_latest()

            frame = cv2.flip(frame,-1)

            if PROCESS_FLIP:
                frame = cv2.flip(frame, 1)

            now = time.time()

            # Update screen mapper (AprilTag detection)
            mapper.update(frame)

            # Process hands with MediaPipe
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            results = hands.process(rgb)

            # Get gesture detection results
            gesture_data = process_hands(
                frame, results, states, clap_detector, stretch_detector, now
            )

            # Get active finger position for screen mapping (pointer or pinch)
            finger_pos = get_active_finger(gesture_data.detected)
            screen_result: ScreenResult | None = None

            if finger_pos:
                screen_result = mapper.find_screen(*finger_pos)
                if screen_result:
                    gesture_data.overlay.append(
                        f"Screen {screen_result.screen_idx}: "
                        f"({screen_result.rel_x:.3f}, {screen_result.rel_y:.3f})"
                    )

            # Send gesture data to UDP backend
            backend.process_frame(
                detected=gesture_data.detected,
                screen_result=screen_result,
                clap_active=gesture_data.clap_active,
                stretch_active=gesture_data.stretch_active,
                stretch_cumulative=gesture_data.stretch_cumulative,
                swipe_detected=gesture_data.swipe_detected,
                swipe_direction=gesture_data.swipe_direction,
            )

            # Render screen boundaries and finger marker
            display.render(frame, mapper, finger_pos, screen_result)

            # Display
            display_frame = cv2.flip(frame, 1) if DISPLAY_FLIP else frame
            _draw_overlay(display_frame, gesture_data.overlay)

            key = display.show(display_frame)
            if key in (ord("q"), 27):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Integrated Hand Gesture + Screen Tracker")
    parser.add_argument("-c", "--camera", type=int, default=0, help="Camera index")
    parser.add_argument("--no-udp", action="store_true", help="Disable UDP backend")
    parser.add_argument("--udp-ip", type=str, default="127.0.0.1", help="UDP target IP")
    parser.add_argument("--udp-port", type=int, default=9090, help="UDP gesture port")
    parser.add_argument("--broadcast", action="store_true", help="Use UDP broadcast mode")
    args = parser.parse_args()

    run_integrated_tracker(
        camera_index=args.camera,
        enable_udp=not args.no_udp,
        udp_ip=args.udp_ip,
        udp_gesture_port=args.udp_port,
        broadcast=args.broadcast,
    )
