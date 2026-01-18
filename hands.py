"""
Hand gesture recognition application.

Detects: Pointer, Pinch, TwoFingerSwipe, Stretch, HandRot, Clap
"""

import cv2
import mediapipe as mp
import time

from src.hand_gestures import (
    VIEW_MODE, MAX_NUM_HANDS,
    HandFeatures,
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

mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands


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
    x0, y0, line_h = 12, 22, 22
    max_chars = max(len(s) for s in overlay)
    box_w = min(16 + max_chars * 9, frame.shape[1] - 24)
    box_h = 12 + line_h * len(overlay)

    cv2.rectangle(frame, (8, 8), (8 + box_w, 8 + box_h), (0, 0, 0), -1)
    for i, s in enumerate(overlay):
        cv2.putText(frame, s, (x0, y0 + i * line_h),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open webcam.")
        return

    # Per-hand state
    states = {k: HandState(label=k) for k in ["Left", "Right", "Unknown"]}
    
    # Two-hand gesture detectors
    clap_detector = ClapDetector()
    stretch_detector = StretchDetector()

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=MAX_NUM_HANDS,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as hands:

        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                continue

            if PROCESS_FLIP:
                frame = cv2.flip(frame, 1)

            h, w = frame.shape[:2]
            now = time.time()

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            results = hands.process(rgb)

            detected: list[DetectedHand] = []
            overlay = [f"Mode: {VIEW_MODE.value}"]

            # Process detected hands
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
            for d in detected:
                state = states[d.label]
                suppressed = clap_active or clap_intent or d.thumbrot or d.pinch
                update_two_finger_swipe(state, d.feats, now, d.two_finger, suppressed)

            # Stretch detection
            stretch_active, stretch_delta, stretch_speed, stretch_cumulative = (
                stretch_detector.update(detected, now, STRETCH_REQUIRE_POINTERS)
            )
            if stretch_active:
                p0, p1 = detected[0].feats.index_tip_px, detected[1].feats.index_tip_px
                cv2.line(frame, p0, p1, (255, 255, 255), 2)
                overlay.append(f"Stretch Δ: {stretch_delta:+.1f}px  ({stretch_speed:+.0f}px/s)")
                overlay.append(f"Stretch Σ: {stretch_cumulative:+.1f}px")

            # Build overlay text
            if detected:
                for d in detected:
                    state = states[d.label]
                    disp = _get_display_label(d, state, now)

                    if d.thumbrot and d.yaw is not None:
                        overlay.append(f"{d.label}: {disp}  yaw={d.yaw:+.1f}  pitch={d.pitch:+.1f}  roll={d.roll:+.1f}")
                    else:
                        overlay.append(f"{d.label}: {disp}")

                    if d.pointer:
                        ix, iy = d.feats.index_tip_px
                        overlay.append(f"  Ptr: ({ix},{iy})")
            else:
                overlay.append("No hands detected")

            # Display
            display_frame = cv2.flip(frame, 1) if DISPLAY_FLIP else frame
            _draw_overlay(display_frame, overlay)
            cv2.imshow("Gestures: Pointer / Pinch / TwoFingerSwipe / StretchDelta / HandRot / Clap", display_frame)

            if cv2.waitKey(1) & 0xFF in (27, ord('q')):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
