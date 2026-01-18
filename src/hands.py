import cv2
import mediapipe as mp
import time
import math
from collections import deque, Counter

# ==========================================================
# VIEW MODE
#   - "FPV_BEHIND_HANDS": camera is first-person, behind hands
#   - "SELFIE_WEBCAM": laptop webcam selfie/mirrored feel
# ==========================================================
VIEW_MODE = "FPV_BEHIND_HANDS"

# If your camera feed is mirrored by the device/app, set this True.
# (Most FPV/back cameras are NOT mirrored -> keep False.)
FORCE_MIRROR_INPUT = False

if VIEW_MODE == "FPV_BEHIND_HANDS":
    DISPLAY_FLIP = False
    PROCESS_FLIP = False
    INVERT_LEFT_RIGHT = False
elif VIEW_MODE == "SELFIE_WEBCAM":
    # Mirror for typical selfie UX (like many webcam demos)
    DISPLAY_FLIP = True
    PROCESS_FLIP = True
    INVERT_LEFT_RIGHT = False
else:
    raise ValueError("Unknown VIEW_MODE")

# If input is already mirrored by your camera pipeline, you can override:
if FORCE_MIRROR_INPUT:
    DISPLAY_FLIP = not DISPLAY_FLIP
    PROCESS_FLIP = not PROCESS_FLIP
    INVERT_LEFT_RIGHT = not INVERT_LEFT_RIGHT

MAX_NUM_HANDS = 2

# =========================
# Gesture thresholds
# =========================
PINCH_THRESH = 0.23
TWO_FINGER_PINCH_THRESH = 0.25

ROTATE_ANGLE_THRESH_DEG = 22
ROTATE_COOLDOWN_S = 0.6

SWIPE_SPEED_PX_S = 1300
SWIPE_DIST_PX = 120
SWIPE_WINDOW_S = 0.22
SWIPE_COOLDOWN_S = 0.6

STABILITY_FRAMES = 3

# =========================
# MediaPipe setup
# =========================
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_hands = mp.solutions.hands

# =========================
# Helpers
# =========================
def dist2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def invert_lr(direction: str) -> str:
    if not INVERT_LEFT_RIGHT:
        return direction
    if direction == "Left":
        return "Right"
    if direction == "Right":
        return "Left"
    return direction

def angle_deg(p1, p2):
    return math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))

def is_finger_extended(wrist, tip, pip):
    d_tip = dist2(wrist, tip)
    d_pip = dist2(wrist, pip)
    return d_tip > d_pip * 1.10

def handedness_label(handedness):
    try:
        return handedness.classification[0].label  # "Left" / "Right"
    except Exception:
        return "Unknown"

def mode_of_last(dq):
    if not dq:
        return None
    c = Counter(dq)
    return c.most_common(1)[0][0]

def mean_point(points):
    x = sum(p[0] for p in points) / len(points)
    y = sum(p[1] for p in points) / len(points)
    return (int(x), int(y))

# =========================
# Gesture classification
# =========================
def classify_hand(pts, hand_scale):
    WRIST = 0
    TH_TIP, TH_IP, TH_MCP = 4, 3, 2
    IX_TIP, IX_PIP, IX_MCP = 8, 6, 5
    MD_TIP, MD_PIP, MD_MCP = 12, 10, 9
    RG_TIP, RG_PIP = 16, 14
    PK_TIP, PK_PIP, PK_MCP = 20, 18, 17

    wrist = pts[WRIST]
    thumb_tip = pts[TH_TIP]
    index_tip = pts[IX_TIP]
    middle_tip = pts[MD_TIP]

    index_ext  = is_finger_extended(wrist, pts[IX_TIP], pts[IX_PIP])
    middle_ext = is_finger_extended(wrist, pts[MD_TIP], pts[MD_PIP])
    ring_ext   = is_finger_extended(wrist, pts[RG_TIP], pts[RG_PIP])
    pinky_ext  = is_finger_extended(wrist, pts[PK_TIP], pts[PK_PIP])
    thumb_ext  = is_finger_extended(wrist, pts[TH_TIP], pts[TH_IP])

    pinch_d = dist2(thumb_tip, index_tip) / max(hand_scale, 1.0)
    pinch = pinch_d < PINCH_THRESH

    two_finger_pinch = (
        (dist2(thumb_tip, index_tip) / max(hand_scale, 1.0) < TWO_FINGER_PINCH_THRESH) and
        (dist2(thumb_tip, middle_tip) / max(hand_scale, 1.0) < TWO_FINGER_PINCH_THRESH)
    )

    extended_count = sum([index_ext, middle_ext, ring_ext, pinky_ext])

    open_palm = (extended_count >= 4) and (dist2(pts[IX_MCP], pts[PK_MCP]) / max(hand_scale, 1.0) > 0.7)

    closed_fist = (extended_count == 0) and (dist2(pts[IX_TIP], wrist) / max(hand_scale, 1.0) < 2.3)

    pointer = index_ext and (not middle_ext) and (not ring_ext) and (not pinky_ext) and (not pinch) and (not two_finger_pinch)

    thumbs_up = False
    thumbs_down = False
    if thumb_ext and (extended_count == 0):
        v = (thumb_tip[0] - pts[TH_MCP][0], thumb_tip[1] - pts[TH_MCP][1])
        v_len = math.hypot(v[0], v[1]) + 1e-6
        v_unit = (v[0] / v_len, v[1] / v_len)

        # image coords: up is negative y
        verticality = abs(v_unit[1])
        if verticality > 0.70 and v_unit[1] < -0.70:
            thumbs_up = True
        elif verticality > 0.70 and v_unit[1] > 0.70:
            thumbs_down = True

    # "Rotate fist" = tilt in image plane when fist is closed
    rotate_dir = None
    rotate_angle = angle_deg(pts[IX_MCP], pts[PK_MCP])
    if closed_fist:
        if rotate_angle > ROTATE_ANGLE_THRESH_DEG:
            rotate_dir = "Right"
        elif rotate_angle < -ROTATE_ANGLE_THRESH_DEG:
            rotate_dir = "Left"

    if two_finger_pinch:
        gesture = "Two-Finger Pinch"
    elif pinch:
        gesture = "Pinch"
    elif thumbs_up:
        gesture = "Thumbs Up"
    elif thumbs_down:
        gesture = "Thumbs Down"
    elif closed_fist:
        gesture = "Closed Fist"
    elif open_palm:
        gesture = "Open Palm"
    elif pointer:
        gesture = "Pointer"
    else:
        gesture = "Unknown"

    # Palm center for more stable swipe tracking (wrist + knuckles)
    palm_center = mean_point([pts[WRIST], pts[IX_MCP], pts[PK_MCP]])

    return {
        "gesture": gesture,
        "pointer": pointer,
        "pinch": pinch,
        "two_finger_pinch": two_finger_pinch,
        "closed_fist": closed_fist,
        "open_palm": open_palm,
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "rotate_dir": rotate_dir,
        "rotate_angle": rotate_angle,
        "index_tip": index_tip,
        "wrist": wrist,
        "palm_center": palm_center,
    }

# =========================
# Main loop
# =========================
def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open webcam.")
        return

    gesture_hist = {"Left": deque(maxlen=STABILITY_FRAMES),
                    "Right": deque(maxlen=STABILITY_FRAMES),
                    "Unknown": deque(maxlen=STABILITY_FRAMES)}
    stable_gesture = {"Left": None, "Right": None, "Unknown": None}

    swipe_track = {"Left": deque(), "Right": deque(), "Unknown": deque()}
    swipe_last_time = {"Left": 0.0, "Right": 0.0, "Unknown": 0.0}

    rotate_last_time = {"Left": 0.0, "Right": 0.0, "Unknown": 0.0}

    print(f"Running in VIEW_MODE={VIEW_MODE}, DISPLAY_FLIP={DISPLAY_FLIP}, PROCESS_FLIP={PROCESS_FLIP}, INVERT_LEFT_RIGHT={INVERT_LEFT_RIGHT}")

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=MAX_NUM_HANDS,
        model_complexity=0,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as hands:

        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                print("Ignoring empty camera frame.")
                continue

            # Optional flip for processing (depends on view mode)
            if PROCESS_FLIP:
                frame = cv2.flip(frame, 1)

            h, w, _ = frame.shape
            now = time.time()

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            results = hands.process(rgb)

            detected = []
            overlay_lines = [f"Mode: {VIEW_MODE}"]

            if results.multi_hand_landmarks:
                for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    label = "Unknown"
                    if results.multi_handedness and i < len(results.multi_handedness):
                        label = handedness_label(results.multi_handedness[i])

                    pts = []
                    for lm in hand_landmarks.landmark:
                        x_px = int(lm.x * w)
                        y_px = int(lm.y * h)
                        pts.append((x_px, y_px))

                    hand_scale = dist2(pts[5], pts[17])
                    hand_scale = max(hand_scale, 60.0)

                    info = classify_hand(pts, hand_scale)
                    info["label"] = label
                    detected.append(info)

                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                        mp_drawing_styles.get_default_hand_landmarks_style(),
                        mp_drawing_styles.get_default_hand_connections_style()
                    )

                    # Pointer "cursor"
                    if info["pointer"] or info["pinch"] or info["two_finger_pinch"]:
                        cv2.circle(frame, info["index_tip"], 10, (0, 255, 0), -1)

                    # Stabilize gesture label
                    gesture_hist[label].append(info["gesture"])
                    g_stable = mode_of_last(gesture_hist[label])
                    if g_stable != stable_gesture[label]:
                        stable_gesture[label] = g_stable
                        print(f"[{time.strftime('%H:%M:%S')}] {label}: {g_stable}")

                    # SWIPE tracking using palm_center.x (more stable in FPV)
                    swipe_track[label].append((now, info["palm_center"][0]))
                    while swipe_track[label] and (now - swipe_track[label][0][0]) > SWIPE_WINDOW_S:
                        swipe_track[label].popleft()

                    if (now - swipe_last_time[label]) > SWIPE_COOLDOWN_S and len(swipe_track[label]) >= 2:
                        t0, x0 = swipe_track[label][0]
                        t1, x1 = swipe_track[label][-1]
                        dt = max(t1 - t0, 1e-6)
                        dx = x1 - x0
                        speed = dx / dt

                        # Only detect swipe if palm is open OR pointer is active (reduces false positives)
                        if (abs(speed) > SWIPE_SPEED_PX_S) and (abs(dx) > SWIPE_DIST_PX) and (info["open_palm"] or info["pointer"]):
                            swipe_dir = "Right" if speed > 0 else "Left"
                            swipe_dir = invert_lr(swipe_dir)
                            swipe_last_time[label] = now
                            print(f"[{time.strftime('%H:%M:%S')}] {label}: Swipe {swipe_dir}")

                    # ROTATE (discrete) with cooldown
                    if info["rotate_dir"] is not None:
                        if (now - rotate_last_time[label]) > ROTATE_COOLDOWN_S:
                            rot_dir = invert_lr(info["rotate_dir"])
                            rotate_last_time[label] = now
                            print(f"[{time.strftime('%H:%M:%S')}] {label}: Rotate {rot_dir} (angle={info['rotate_angle']:.1f}°)")

            # Two-hand stretch (continuous)
            stretch_text = None
            if len(detected) == 2 and detected[0]["pointer"] and detected[1]["pointer"]:
                p0 = detected[0]["index_tip"]
                p1 = detected[1]["index_tip"]
                d = dist2(p0, p1)
                diag = math.hypot(w, h)
                stretch_norm = clamp(d / diag, 0.0, 1.0)
                stretch_text = f"Stretch: {d:.0f}px ({stretch_norm:.3f})"
                cv2.line(frame, p0, p1, (255, 255, 255), 2)

            # Overlay text
            if detected:
                for info in detected:
                    label = info["label"]
                    g = stable_gesture[label] if stable_gesture[label] else info["gesture"]
                    line = f"{label}: {g}"
                    if info["pointer"]:
                        x, y = info["index_tip"]
                        line += f" | Ptr=({x},{y})"
                    overlay_lines.append(line)
            else:
                overlay_lines.append("No hands detected")

            if stretch_text:
                overlay_lines.append(stretch_text)

            # Flip ONLY for display if desired (usually false in FPV)
            display_frame = cv2.flip(frame, 1) if DISPLAY_FLIP else frame

            # Draw overlay box
            x0, y0 = 12, 22
            line_h = 22
            max_chars = max(len(s) for s in overlay_lines)
            box_px_w = min(16 + max_chars * 9, display_frame.shape[1] - 24)
            box_px_h = 12 + line_h * len(overlay_lines)

            cv2.rectangle(display_frame, (8, 8), (8 + box_px_w, 8 + box_px_h), (0, 0, 0), -1)
            for i, s in enumerate(overlay_lines):
                cv2.putText(
                    display_frame,
                    s,
                    (x0, y0 + i * line_h),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA
                )

            cv2.imshow("MediaPipe Hands - Gestures", display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
