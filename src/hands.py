import cv2
import mediapipe as mp
import time
import math
from collections import deque

VIEW_MODE = "FPV_BEHIND_HANDS"   # "SELFIE_WEBCAM"
FORCE_MIRROR_INPUT = False
INVERT_HANDEDNESS = True
MAX_NUM_HANDS = 2

PINCH_LATCH_S = 0.30
CLAP_LATCH_S = 0.65
TWO_FINGER_SWIPE_LATCH_S = 0.45
CLAP_COOLDOWN_S = 0.70

PINCH_ON = 0.62
PINCH_OFF = 0.80
PINCH_STILL_LOG_INTERVAL_S = 0.35

EXT_MIN_PIP_ANGLE_DEG = 158.0
FINGER_EXT_TIP_RATIO_3 = 0.90
CURL_MAX_PIP_ANGLE_DEG = 152.0
FINGER_CURLED_TIP_RATIO_3 = 0.84

POINTER_REQUIRE_ONLY_INDEX = True

THUMB_MIN_IP_ANGLE_DEG = 162.0
THUMB_TIP_RATIO_3 = 1.10
THUMBS_UP_MIN_VY = -0.88
THUMBS_UP_MAX_VX = 0.28
THUMBS_UP_MAX_VZ = 0.35
THUMBS_ENTER_FRAMES = 8
THUMBS_EXIT_FRAMES = 6
THUMBS_LOG_INTERVAL_S = 0.25
THUMBS_REQUIRE_CURLED_FINGERS = 3
THUMBS_BLOCK_IF_POINTER = True

CLAP_ARM_RATIO = 1.90
CLAP_NEAR_RATIO = 0.78
LAST_SEEN_WINDOW_S = 0.30
CLAP_INTENT_RATIO = 1.35
CLAP_INTENT_APPROACH = 1.4

TFS_WINDOW_S = 0.30
TFS_MIN_PEAK_SPEED_PX_S = 900
TFS_MIN_PEAK_DIST_PX = 90
TFS_COOLDOWN_S = 0.55
TFS_DIR_CONSISTENCY_MIN = 0.55
TFS_MIN_ANGLE_DELTA_DEG = 10.0
TFS_MIN_ANGLE_SPEED_DEG_S = 80.0
TFS_STRONG_DIST_PX = 180
TFS_STRONG_SPEED_PX_S = 1600

STRETCH_REQUIRE_POINTERS = True

if VIEW_MODE == "FPV_BEHIND_HANDS":
    DISPLAY_FLIP = False
    PROCESS_FLIP = False
elif VIEW_MODE == "SELFIE_WEBCAM":
    DISPLAY_FLIP = True
    PROCESS_FLIP = True
else:
    raise ValueError("Unknown VIEW_MODE")

if FORCE_MIRROR_INPUT:
    DISPLAY_FLIP = not DISPLAY_FLIP
    PROCESS_FLIP = not PROCESS_FLIP

mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_hands = mp.solutions.hands


def dist2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def dist3(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def mean_point2(points):
    x = sum(p[0] for p in points) / len(points)
    y = sum(p[1] for p in points) / len(points)
    return (int(x), int(y))


def mean_point3(points):
    x = sum(p[0] for p in points) / len(points)
    y = sum(p[1] for p in points) / len(points)
    z = sum(p[2] for p in points) / len(points)
    return (x, y, z)


def sub3(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross3(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def norm3(a):
    return math.sqrt(dot3(a, a)) + 1e-9


def normalize3(a):
    n = norm3(a)
    return (a[0] / n, a[1] / n, a[2] / n)


def angle_3pt_deg(a, b, c):
    bax = (a[0] - b[0], a[1] - b[1], a[2] - b[2])
    bcx = (c[0] - b[0], c[1] - b[1], c[2] - b[2])
    ba_len = norm3(bax)
    bc_len = norm3(bcx)
    cosang = clamp(dot3(bax, bcx) / (ba_len * bc_len), -1.0, 1.0)
    return math.degrees(math.acos(cosang))


def update_hysteresis(active, value, on_thr, off_thr):
    if not active:
        return value <= on_thr
    return not (value >= off_thr)


def handedness_label(h):
    try:
        lbl = h.classification[0].label
    except Exception:
        lbl = "Unknown"
    if INVERT_HANDEDNESS:
        if lbl == "Left":
            return "Right"
        if lbl == "Right":
            return "Left"
    return lbl


def yaw_pitch_from_vec(vx, vy, vz):
    forward = max(1e-6, -vz)
    yaw = math.degrees(math.atan2(vx, forward))
    pitch = math.degrees(math.atan2(-vy, forward))
    return yaw, pitch


def hand_orientation_angles(wrist3, index_mcp3, pinky_mcp3, middle_mcp3):
    across = normalize3(sub3(index_mcp3, pinky_mcp3))
    forward = normalize3(sub3(middle_mcp3, wrist3))
    normal = normalize3(cross3(across, forward))

    yaw, pitch = yaw_pitch_from_vec(forward[0], forward[1], forward[2])

    roll = math.degrees(math.atan2(across[1], across[0]))
    if roll > 180:
        roll -= 360
    if roll < -180:
        roll += 360

    return yaw, pitch, roll, forward, normal, across


def latch(st, label, now, hold_s):
    st["latched_label"] = label
    st["latched_until"] = max(st["latched_until"], now + hold_s)


def wrap_deg(a):
    return (a + 180.0) % 360.0 - 180.0


def angle_delta_deg(a0, a1):
    return wrap_deg(a1 - a0)


def extract(px, n3):
    WRIST = 0
    TH_MCP, TH_IP, TH_TIP = 2, 3, 4
    IX_MCP, IX_PIP, IX_DIP, IX_TIP = 5, 6, 7, 8
    MD_MCP, MD_PIP, MD_DIP, MD_TIP = 9, 10, 11, 12
    RG_MCP, RG_PIP, RG_DIP, RG_TIP = 13, 14, 15, 16
    PK_MCP, PK_PIP, PK_DIP, PK_TIP = 17, 18, 19, 20

    hand_scale_3 = max(dist3(n3[IX_MCP], n3[PK_MCP]), 1e-3)
    palm_center_3 = mean_point3([n3[WRIST], n3[IX_MCP], n3[MD_MCP], n3[PK_MCP]])
    palm_center_px = mean_point2([px[WRIST], px[IX_MCP], px[MD_MCP], px[PK_MCP]])

    idx_ang = angle_3pt_deg(n3[IX_MCP], n3[IX_PIP], n3[IX_DIP])
    mid_ang = angle_3pt_deg(n3[MD_MCP], n3[MD_PIP], n3[MD_DIP])
    rng_ang = angle_3pt_deg(n3[RG_MCP], n3[RG_PIP], n3[RG_DIP])
    pky_ang = angle_3pt_deg(n3[PK_MCP], n3[PK_PIP], n3[PK_DIP])
    th_ang = angle_3pt_deg(n3[TH_MCP], n3[TH_IP], n3[TH_TIP])

    def tip_ratio_3(tip_i):
        return dist3(n3[tip_i], palm_center_3) / (hand_scale_3 + 1e-9)

    idx_tip_r = tip_ratio_3(IX_TIP)
    mid_tip_r = tip_ratio_3(MD_TIP)
    rng_tip_r = tip_ratio_3(RG_TIP)
    pky_tip_r = tip_ratio_3(PK_TIP)
    th_tip_r = tip_ratio_3(TH_TIP)

    def is_ext(pip_ang, tip_r):
        return (pip_ang >= EXT_MIN_PIP_ANGLE_DEG) and (tip_r >= FINGER_EXT_TIP_RATIO_3)

    def is_curled(pip_ang, tip_r):
        return (pip_ang <= CURL_MAX_PIP_ANGLE_DEG) or (tip_r <= FINGER_CURLED_TIP_RATIO_3)

    index_ext = is_ext(idx_ang, idx_tip_r)
    middle_ext = is_ext(mid_ang, mid_tip_r)
    ring_ext = is_ext(rng_ang, rng_tip_r)
    pinky_ext = is_ext(pky_ang, pky_tip_r)

    index_curled = is_curled(idx_ang, idx_tip_r)
    middle_curled = is_curled(mid_ang, mid_tip_r)
    ring_curled = is_curled(rng_ang, rng_tip_r)
    pinky_curled = is_curled(pky_ang, pky_tip_r)

    thumb_vec = normalize3(sub3(n3[TH_TIP], n3[TH_MCP]))
    thumb_strong = (th_ang >= THUMB_MIN_IP_ANGLE_DEG) and (th_tip_r >= THUMB_TIP_RATIO_3)

    wx, wy = px[WRIST]
    mx, my = px[MD_MCP]
    flick_angle_deg = math.degrees(math.atan2((my - wy), (mx - wx)))

    return {
        "hand_scale_3": hand_scale_3,
        "palm_center_3": palm_center_3,
        "palm_center_px": palm_center_px,
        "flick_angle_deg": flick_angle_deg,

        "wrist_3": n3[WRIST],
        "index_mcp_3": n3[IX_MCP],
        "pinky_mcp_3": n3[PK_MCP],
        "middle_mcp_3": n3[MD_MCP],

        "index_tip_px": px[IX_TIP],
        "middle_tip_px": px[MD_TIP],
        "index_tip_3": n3[IX_TIP],
        "thumb_tip_3": n3[TH_TIP],

        "index_ext": index_ext,
        "middle_ext": middle_ext,
        "ring_ext": ring_ext,
        "pinky_ext": pinky_ext,

        "index_curled": index_curled,
        "middle_curled": middle_curled,
        "ring_curled": ring_curled,
        "pinky_curled": pinky_curled,

        "thumb_vec_u": thumb_vec,
        "thumb_strong": thumb_strong,
    }


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open webcam.")
        return

    state = {k: {
        "latched_label": "Neutral",
        "latched_until": 0.0,

        "pinch_active": False,
        "pinch_prev": False,
        "last_pinch_still_log": 0.0,

        "thumbs_active": False,
        "thumbs_enter": 0,
        "thumbs_exit": 0,
        "last_thumb_log": 0.0,

        "tfs_track": deque(),
        "tfs_cooldown_until": 0.0,
    } for k in ["Left", "Right", "Unknown"]}

    clap_latched_until = 0.0
    clap_cooldown_until = 0.0
    clap_armed = True
    pair_hist = deque(maxlen=6)

    last_seen = {
        "Left": {"t": 0.0, "palm3": None, "scale3": None},
        "Right": {"t": 0.0, "palm3": None, "scale3": None},
    }

    stretch_prev_dpx = None
    stretch_prev_t = None
    stretch_cumulative_px = 0.0

    def last_valid(hand_key, now):
        return (now - last_seen[hand_key]["t"]) <= LAST_SEEN_WINDOW_S and last_seen[hand_key]["palm3"] is not None

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

            h, w, _ = frame.shape
            now = time.time()

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            results = hands.process(rgb)

            detected = []
            overlay = [f"Mode: {VIEW_MODE}"]

            used_labels = set()
            if results.multi_hand_landmarks:
                for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    lbl = "Unknown"
                    if results.multi_handedness and i < len(results.multi_handedness):
                        lbl = handedness_label(results.multi_handedness[i])

                    if lbl in used_labels:
                        if "Left" not in used_labels:
                            lbl = "Left"
                        elif "Right" not in used_labels:
                            lbl = "Right"
                        else:
                            lbl = "Unknown"
                    used_labels.add(lbl)

                    px, n3 = [], []
                    for lm in hand_landmarks.landmark:
                        px.append((int(lm.x * w), int(lm.y * h)))
                        n3.append((lm.x, lm.y, lm.z))

                    feats = extract(px, n3)
                    st = state[lbl]

                    if lbl in ("Left", "Right"):
                        last_seen[lbl]["t"] = now
                        last_seen[lbl]["palm3"] = feats["palm_center_3"]
                        last_seen[lbl]["scale3"] = feats["hand_scale_3"]

                    if POINTER_REQUIRE_ONLY_INDEX:
                        pointer = feats["index_ext"] and (not feats["middle_ext"]) and (not feats["ring_ext"]) and (not feats["pinky_ext"])
                    else:
                        pointer = feats["index_ext"]

                    two_finger_pose = feats["index_ext"] and feats["middle_ext"] and feats["ring_curled"] and feats["pinky_curled"]

                    vx, vy, vz = feats["thumb_vec_u"]
                    thumbs_up_dir = (vy <= THUMBS_UP_MIN_VY) and (abs(vx) <= THUMBS_UP_MAX_VX) and (abs(vz) <= THUMBS_UP_MAX_VZ)
                    curled_count = sum([feats["index_curled"], feats["middle_curled"], feats["ring_curled"], feats["pinky_curled"]])

                    thumbs_candidate = feats["thumb_strong"] and thumbs_up_dir and (curled_count >= THUMBS_REQUIRE_CURLED_FINGERS)
                    if THUMBS_BLOCK_IF_POINTER and pointer:
                        thumbs_candidate = False

                    if thumbs_candidate:
                        st["thumbs_enter"] = min(THUMBS_ENTER_FRAMES, st["thumbs_enter"] + 1)
                        st["thumbs_exit"] = 0
                    else:
                        st["thumbs_exit"] = min(THUMBS_EXIT_FRAMES, st["thumbs_exit"] + 1)
                        st["thumbs_enter"] = 0

                    if (not st["thumbs_active"]) and st["thumbs_enter"] >= THUMBS_ENTER_FRAMES:
                        st["thumbs_active"] = True
                        print(f"[{time.strftime('%H:%M:%S')}] {lbl}: ENTER ThumbRot")
                    elif st["thumbs_active"] and st["thumbs_exit"] >= THUMBS_EXIT_FRAMES:
                        st["thumbs_active"] = False
                        print(f"[{time.strftime('%H:%M:%S')}] {lbl}: EXIT ThumbRot")

                    yaw_deg = pitch_deg = roll_deg = None
                    if st["thumbs_active"]:
                        yaw_deg, pitch_deg, roll_deg, _, _, _ = hand_orientation_angles(
                            feats["wrist_3"], feats["index_mcp_3"], feats["pinky_mcp_3"], feats["middle_mcp_3"]
                        )
                        if (now - st["last_thumb_log"]) >= THUMBS_LOG_INTERVAL_S:
                            st["last_thumb_log"] = now
                            print(f"[{time.strftime('%H:%M:%S')}] {lbl}: HandRot yaw={yaw_deg:+.1f} pitch={pitch_deg:+.1f} roll={roll_deg:+.1f}")

                    thumb_index = dist3(feats["thumb_tip_3"], feats["index_tip_3"]) / feats["hand_scale_3"]
                    if st["thumbs_active"] or two_finger_pose:
                        if st["pinch_active"]:
                            print(f"[{time.strftime('%H:%M:%S')}] {lbl}: Pinch RELEASED (mode override)")
                        st["pinch_active"] = False
                        st["pinch_prev"] = False
                    else:
                        st["pinch_active"] = update_hysteresis(st["pinch_active"], thumb_index, PINCH_ON, PINCH_OFF)

                        if (not st["pinch_prev"]) and st["pinch_active"]:
                            latch(st, "Pinch", now, PINCH_LATCH_S)
                            print(f"[{time.strftime('%H:%M:%S')}] {lbl}: Pinch START")

                        if st["pinch_active"]:
                            if (now - st["last_pinch_still_log"]) >= PINCH_STILL_LOG_INTERVAL_S:
                                st["last_pinch_still_log"] = now
                                print(f"[{time.strftime('%H:%M:%S')}] {lbl}: STILL PINCHING")

                        if st["pinch_prev"] and (not st["pinch_active"]):
                            print(f"[{time.strftime('%H:%M:%S')}] {lbl}: Pinch RELEASED")

                        st["pinch_prev"] = st["pinch_active"]

                    if st["pinch_active"]:
                        pointer = False

                    mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                    # Optional: draw small green circles at each joint
                    for lm in hand_landmarks.landmark:
                        cx, cy = int(lm.x * w), int(lm.y * h)
                        cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)

                    if pointer or st["pinch_active"]:
                        cv2.circle(frame, feats["index_tip_px"], 10, (0, 255, 0), -1)

                    detected.append({
                        "label": lbl,
                        "feats": feats,
                        "pointer": pointer,
                        "two_finger": two_finger_pose,
                        "pinch": st["pinch_active"],
                        "thumbrot": st["thumbs_active"],
                        "yaw": yaw_deg,
                        "pitch": pitch_deg,
                        "roll": roll_deg
                    })

            clap_active = now < clap_latched_until

            def compute_pair_ratio():
                if len(detected) == 2:
                    p0 = detected[0]["feats"]["palm_center_3"]
                    p1 = detected[1]["feats"]["palm_center_3"]
                    s0 = detected[0]["feats"]["hand_scale_3"]
                    s1 = detected[1]["feats"]["hand_scale_3"]
                    avg = (s0 + s1) / 2.0
                    return dist3(p0, p1) / (avg + 1e-9)
                if last_valid("Left", now) and last_valid("Right", now):
                    p0 = last_seen["Left"]["palm3"]
                    p1 = last_seen["Right"]["palm3"]
                    avg = (last_seen["Left"]["scale3"] + last_seen["Right"]["scale3"]) / 2.0
                    return dist3(p0, p1) / (avg + 1e-9)
                return None

            pair_ratio = compute_pair_ratio()
            approach = 0.0
            if pair_ratio is not None:
                pair_hist.append((now, pair_ratio))
                if len(pair_hist) >= 2:
                    t0, r0 = pair_hist[0]
                    t1, r1 = pair_hist[-1]
                    dt = max(t1 - t0, 1e-6)
                    approach = (r0 - r1) / dt

            clap_intent = (pair_ratio is not None) and ((pair_ratio <= CLAP_INTENT_RATIO) or (approach >= CLAP_INTENT_APPROACH))

            if pair_ratio is not None and pair_ratio >= CLAP_ARM_RATIO:
                clap_armed = True

            if (not clap_active) and clap_armed and (now >= clap_cooldown_until) and (pair_ratio is not None):
                if pair_ratio <= CLAP_NEAR_RATIO:
                    clap_latched_until = now + CLAP_LATCH_S
                    clap_cooldown_until = now + CLAP_COOLDOWN_S
                    clap_armed = False
                    clap_active = True
                    print(f"[{time.strftime('%H:%M:%S')}] GLOBAL: Clap")

            if clap_active:
                overlay.append("GLOBAL: Clap")

            for d in detected:
                lbl = d["label"]
                feats = d["feats"]
                st = state[lbl]

                two_finger = d["two_finger"]
                suppressed = clap_active or clap_intent or d["thumbrot"] or d["pinch"]

                if (not two_finger) or suppressed:
                    st["tfs_track"].clear()
                    continue

                if now < st["tfs_cooldown_until"]:
                    st["tfs_track"].clear()
                    continue

                x_tips = 0.5 * (feats["index_tip_px"][0] + feats["middle_tip_px"][0])
                palm_x = feats["palm_center_px"][0]
                x = 0.65 * x_tips + 0.35 * palm_x

                ang = feats["flick_angle_deg"]
                st["tfs_track"].append((now, x, ang))

                while st["tfs_track"] and (now - st["tfs_track"][0][0]) > TFS_WINDOW_S:
                    st["tfs_track"].popleft()

                if len(st["tfs_track"]) >= 3:
                    t0, x0, a0 = st["tfs_track"][0]
                    t1, x1, a1 = st["tfs_track"][-1]
                    dt = max(t1 - t0, 1e-6)

                    xs = [p[1] for p in st["tfs_track"]]
                    peak_dx = (max(xs) - min(xs))
                    net_dx = x1 - x0
                    consistency = abs(net_dx) / (peak_dx + 1e-6)
                    peak_speed = peak_dx / dt

                    da = angle_delta_deg(a0, a1)
                    ang_speed = abs(da) / dt

                    flick_ok = (abs(da) >= TFS_MIN_ANGLE_DELTA_DEG) and (ang_speed >= TFS_MIN_ANGLE_SPEED_DEG_S)
                    strong_motion_ok = (peak_dx >= TFS_STRONG_DIST_PX) and (peak_speed >= TFS_STRONG_SPEED_PX_S)

                    if (peak_dx >= TFS_MIN_PEAK_DIST_PX and
                        peak_speed >= TFS_MIN_PEAK_SPEED_PX_S and
                        consistency >= TFS_DIR_CONSISTENCY_MIN and
                        (flick_ok or strong_motion_ok)):

                        print(f"[{time.strftime('%H:%M:%S')}] {lbl}: TwoFingerSwipe")
                        latch(st, "TwoFingerSwipe", now, TWO_FINGER_SWIPE_LATCH_S)
                        st["tfs_cooldown_until"] = now + TFS_COOLDOWN_S
                        st["tfs_track"].clear()

            stretch_active = (
                len(detected) == 2 and
                STRETCH_REQUIRE_POINTERS and
                detected[0]["pointer"] and
                detected[1]["pointer"]
            )

            if stretch_active:
                p0 = detected[0]["feats"]["index_tip_px"]
                p1 = detected[1]["feats"]["index_tip_px"]
                dpx = dist2(p0, p1)

                if stretch_prev_dpx is None:
                    stretch_prev_dpx = dpx
                    stretch_prev_t = now
                    stretch_delta_px = 0.0
                    stretch_delta_per_s = 0.0
                else:
                    dt = max(now - (stretch_prev_t or now), 1e-6)
                    stretch_delta_px = dpx - stretch_prev_dpx
                    stretch_delta_per_s = stretch_delta_px / dt
                    stretch_prev_dpx = dpx
                    stretch_prev_t = now
                    stretch_cumulative_px += stretch_delta_px

                cv2.line(frame, p0, p1, (255, 255, 255), 2)
                overlay.append(f"Stretch Δ: {stretch_delta_px:+.1f}px  ({stretch_delta_per_s:+.0f}px/s)")
                overlay.append(f"Stretch Σ: {stretch_cumulative_px:+.1f}px")
            else:
                stretch_prev_dpx = None
                stretch_prev_t = None
                stretch_cumulative_px = 0.0

            if detected:
                for d in detected:
                    lbl = d["label"]
                    st = state[lbl]

                    if d["thumbrot"]:
                        disp = "HandRot"
                    elif now < st["latched_until"]:
                        disp = st["latched_label"]
                    elif d["pinch"]:
                        disp = "Pinch (held)"
                    elif d["two_finger"]:
                        disp = "TwoFinger (ready)"
                    elif d["pointer"]:
                        disp = "Pointer"
                    else:
                        disp = "Neutral"

                    if d["thumbrot"] and d["yaw"] is not None and d["pitch"] is not None and d["roll"] is not None:
                        overlay.append(f"{lbl}: {disp}  yaw={d['yaw']:+.1f}  pitch={d['pitch']:+.1f}  roll={d['roll']:+.1f}")
                    else:
                        overlay.append(f"{lbl}: {disp}")

                    if d["pointer"]:
                        ix, iy = d["feats"]["index_tip_px"]
                        overlay.append(f"  Ptr: ({ix},{iy})")
            else:
                overlay.append("No hands detected")

            display_frame = cv2.flip(frame, 1) if DISPLAY_FLIP else frame
            x0, y0 = 12, 22
            line_h = 22
            max_chars = max(len(s) for s in overlay)
            box_w = min(16 + max_chars * 9, display_frame.shape[1] - 24)
            box_h = 12 + line_h * len(overlay)

            cv2.rectangle(display_frame, (8, 8), (8 + box_w, 8 + box_h), (0, 0, 0), -1)
            for i, s in enumerate(overlay):
                cv2.putText(display_frame, s, (x0, y0 + i * line_h),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

            cv2.imshow("Gestures: Pointer / Pinch / TwoFingerSwipe / StretchDelta / HandRot / Clap", display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
