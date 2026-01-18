"""Gesture detection classes for hand tracking."""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from .math_utils import dist2, dist3, angle_delta_deg, update_hysteresis
from .features import HandFeatures, hand_orientation_angles
from .config import (
    PINCH_ON, PINCH_OFF, PINCH_LATCH_S, PINCH_STILL_LOG_INTERVAL_S,
    THUMBS_UP_MIN_VY, THUMBS_UP_MAX_VX, THUMBS_UP_MAX_VZ,
    THUMBS_ENTER_FRAMES, THUMBS_EXIT_FRAMES, THUMBS_LOG_INTERVAL_S,
    THUMBS_REQUIRE_CURLED_FINGERS, THUMBS_BLOCK_IF_POINTER,
    CLAP_ARM_RATIO, CLAP_NEAR_RATIO, CLAP_LATCH_S, CLAP_COOLDOWN_S,
    CLAP_INTENT_RATIO, CLAP_INTENT_APPROACH, LAST_SEEN_WINDOW_S,
    TFS_WINDOW_S, TFS_MIN_PEAK_DIST_PX, TFS_MIN_PEAK_SPEED_PX_S,
    TFS_COOLDOWN_S, TFS_DIR_CONSISTENCY_MIN,
    TFS_MIN_ANGLE_DELTA_DEG, TFS_MIN_ANGLE_SPEED_DEG_S,
    TFS_STRONG_DIST_PX, TFS_STRONG_SPEED_PX_S, TWO_FINGER_SWIPE_LATCH_S,
    POINTER_REQUIRE_ONLY_INDEX,
)


def _timestamp() -> str:
    return time.strftime('%H:%M:%S')


@dataclass
class HandState:
    """Per-hand gesture state tracking."""
    label: str
    latched_label: str = "Neutral"
    latched_until: float = 0.0

    pinch_active: bool = False
    pinch_prev: bool = False
    last_pinch_still_log: float = 0.0

    thumbs_active: bool = False
    thumbs_enter: int = 0
    thumbs_exit: int = 0
    last_thumb_log: float = 0.0

    tfs_track: deque = field(default_factory=deque)
    tfs_cooldown_until: float = 0.0

    def latch(self, label: str, now: float, hold_s: float):
        """Set latched gesture label with hold duration."""
        self.latched_label = label
        self.latched_until = max(self.latched_until, now + hold_s)


@dataclass
class DetectedHand:
    """Detection result for a single hand."""
    label: str
    feats: HandFeatures
    pointer: bool
    two_finger: bool
    pinch: bool
    thumbrot: bool
    yaw: float | None = None
    pitch: float | None = None
    roll: float | None = None


# =============================================================================
# POSE DETECTION
# =============================================================================

def is_pointer(feats: HandFeatures) -> bool:
    """Check if hand is in pointer pose (index extended, others curled)."""
    if POINTER_REQUIRE_ONLY_INDEX:
        return (feats.index_ext and not feats.middle_ext 
                and not feats.ring_ext and not feats.pinky_ext)
    return feats.index_ext


def is_two_finger_pose(feats: HandFeatures) -> bool:
    """Check if hand is in two-finger pose (index+middle extended, others curled)."""
    return (feats.index_ext and feats.middle_ext 
            and feats.ring_curled and feats.pinky_curled)


# =============================================================================
# PINCH DETECTION
# =============================================================================

def update_pinch(state: HandState, feats: HandFeatures, now: float, suppressed: bool) -> bool:
    """
    Update pinch detection state.
    
    Args:
        state: Per-hand state
        feats: Current hand features
        now: Current timestamp
        suppressed: Whether pinch should be suppressed (e.g., during thumbrot)
    
    Returns:
        Whether pinch is currently active
    """
    if suppressed:
        if state.pinch_active:
            print(f"[{_timestamp()}] {state.label}: Pinch RELEASED (mode override)")
        state.pinch_active = False
        state.pinch_prev = False
        return False

    thumb_index_dist = dist3(feats.thumb_tip_3, feats.index_tip_3) / feats.hand_scale_3
    state.pinch_active = update_hysteresis(state.pinch_active, thumb_index_dist, PINCH_ON, PINCH_OFF)

    if not state.pinch_prev and state.pinch_active:
        state.latch("Pinch", now, PINCH_LATCH_S)
        print(f"[{_timestamp()}] {state.label}: Pinch START")

    if state.pinch_active and (now - state.last_pinch_still_log) >= PINCH_STILL_LOG_INTERVAL_S:
        state.last_pinch_still_log = now
        print(f"[{_timestamp()}] {state.label}: STILL PINCHING")

    if state.pinch_prev and not state.pinch_active:
        print(f"[{_timestamp()}] {state.label}: Pinch RELEASED")

    state.pinch_prev = state.pinch_active
    return state.pinch_active


# =============================================================================
# THUMBS UP / HAND ROTATION
# =============================================================================

def update_thumbrot(
    state: HandState, feats: HandFeatures, now: float, pointer: bool
) -> tuple[bool, float | None, float | None, float | None]:
    """
    Update thumbs-up / hand rotation detection.
    
    Returns:
        (is_active, yaw, pitch, roll) - angles are None if not in thumbrot mode
    """
    vx, vy, vz = feats.thumb_vec_u
    thumbs_up_dir = (vy <= THUMBS_UP_MIN_VY and abs(vx) <= THUMBS_UP_MAX_VX 
                     and abs(vz) <= THUMBS_UP_MAX_VZ)
    
    thumbs_candidate = (feats.thumb_strong and thumbs_up_dir 
                        and feats.curled_count >= THUMBS_REQUIRE_CURLED_FINGERS)
    
    if THUMBS_BLOCK_IF_POINTER and pointer:
        thumbs_candidate = False

    if thumbs_candidate:
        state.thumbs_enter = min(THUMBS_ENTER_FRAMES, state.thumbs_enter + 1)
        state.thumbs_exit = 0
    else:
        state.thumbs_exit = min(THUMBS_EXIT_FRAMES, state.thumbs_exit + 1)
        state.thumbs_enter = 0

    if not state.thumbs_active and state.thumbs_enter >= THUMBS_ENTER_FRAMES:
        state.thumbs_active = True
        print(f"[{_timestamp()}] {state.label}: ENTER ThumbRot")
    elif state.thumbs_active and state.thumbs_exit >= THUMBS_EXIT_FRAMES:
        state.thumbs_active = False
        print(f"[{_timestamp()}] {state.label}: EXIT ThumbRot")

    yaw = pitch = roll = None
    if state.thumbs_active:
        yaw, pitch, roll = hand_orientation_angles(
            feats.wrist_3, feats.index_mcp_3, feats.pinky_mcp_3, feats.middle_mcp_3
        )
        if (now - state.last_thumb_log) >= THUMBS_LOG_INTERVAL_S:
            state.last_thumb_log = now
            print(f"[{_timestamp()}] {state.label}: HandRot yaw={yaw:+.1f} pitch={pitch:+.1f} roll={roll:+.1f}")

    return state.thumbs_active, yaw, pitch, roll


# =============================================================================
# TWO FINGER SWIPE
# =============================================================================

def update_two_finger_swipe(
    state: HandState, feats: HandFeatures, now: float, 
    two_finger: bool, suppressed: bool
) -> bool:
    """
    Update two-finger swipe detection.
    
    Returns:
        Whether a swipe was just detected
    """
    if not two_finger or suppressed or now < state.tfs_cooldown_until:
        state.tfs_track.clear()
        return False

    x_tips = 0.5 * (feats.index_tip_px[0] + feats.middle_tip_px[0])
    palm_x = feats.palm_center_px[0]
    x = 0.65 * x_tips + 0.35 * palm_x
    ang = feats.flick_angle_deg

    state.tfs_track.append((now, x, ang))

    while state.tfs_track and (now - state.tfs_track[0][0]) > TFS_WINDOW_S:
        state.tfs_track.popleft()

    if len(state.tfs_track) < 3:
        return False

    t0, x0, a0 = state.tfs_track[0]
    t1, x1, a1 = state.tfs_track[-1]
    dt = max(t1 - t0, 1e-6)

    xs = [p[1] for p in state.tfs_track]
    peak_dx = max(xs) - min(xs)
    net_dx = x1 - x0
    consistency = abs(net_dx) / (peak_dx + 1e-6)
    peak_speed = peak_dx / dt

    da = angle_delta_deg(a0, a1)
    ang_speed = abs(da) / dt

    flick_ok = abs(da) >= TFS_MIN_ANGLE_DELTA_DEG and ang_speed >= TFS_MIN_ANGLE_SPEED_DEG_S
    strong_motion_ok = peak_dx >= TFS_STRONG_DIST_PX and peak_speed >= TFS_STRONG_SPEED_PX_S

    if (peak_dx >= TFS_MIN_PEAK_DIST_PX and peak_speed >= TFS_MIN_PEAK_SPEED_PX_S
        and consistency >= TFS_DIR_CONSISTENCY_MIN and (flick_ok or strong_motion_ok)):
        print(f"[{_timestamp()}] {state.label}: TwoFingerSwipe")
        state.latch("TwoFingerSwipe", now, TWO_FINGER_SWIPE_LATCH_S)
        state.tfs_cooldown_until = now + TFS_COOLDOWN_S
        state.tfs_track.clear()
        return True

    return False


# =============================================================================
# CLAP DETECTION (TWO-HAND GESTURE)
# =============================================================================

@dataclass
class ClapDetector:
    """Detects clap gestures using both hands."""
    latched_until: float = 0.0
    cooldown_until: float = 0.0
    armed: bool = True
    pair_hist: deque = field(default_factory=lambda: deque(maxlen=6))
    
    last_seen: dict = field(default_factory=lambda: {
        "Left": {"t": 0.0, "palm3": None, "scale3": None},
        "Right": {"t": 0.0, "palm3": None, "scale3": None},
    })

    def _last_valid(self, hand_key: str, now: float) -> bool:
        entry = self.last_seen[hand_key]
        return (now - entry["t"]) <= LAST_SEEN_WINDOW_S and entry["palm3"] is not None

    def update_last_seen(self, label: str, feats: HandFeatures, now: float):
        """Update last-seen data for a hand."""
        if label in ("Left", "Right"):
            self.last_seen[label]["t"] = now
            self.last_seen[label]["palm3"] = feats.palm_center_3
            self.last_seen[label]["scale3"] = feats.hand_scale_3

    def _compute_pair_ratio(self, detected: list[DetectedHand], now: float) -> float | None:
        """Compute distance ratio between hands."""
        if len(detected) == 2:
            p0, p1 = detected[0].feats.palm_center_3, detected[1].feats.palm_center_3
            s0, s1 = detected[0].feats.hand_scale_3, detected[1].feats.hand_scale_3
            return dist3(p0, p1) / ((s0 + s1) / 2.0 + 1e-9)

        if self._last_valid("Left", now) and self._last_valid("Right", now):
            p0, p1 = self.last_seen["Left"]["palm3"], self.last_seen["Right"]["palm3"]
            avg = (self.last_seen["Left"]["scale3"] + self.last_seen["Right"]["scale3"]) / 2.0
            return dist3(p0, p1) / (avg + 1e-9)

        return None

    def update(self, detected: list[DetectedHand], now: float) -> tuple[bool, bool]:
        """
        Update clap detection.
        
        Returns:
            (clap_active, clap_intent) - whether clap is active and whether intent is detected
        """
        clap_active = now < self.latched_until
        pair_ratio = self._compute_pair_ratio(detected, now)

        approach = 0.0
        if pair_ratio is not None:
            self.pair_hist.append((now, pair_ratio))
            if len(self.pair_hist) >= 2:
                t0, r0 = self.pair_hist[0]
                t1, r1 = self.pair_hist[-1]
                approach = (r0 - r1) / max(t1 - t0, 1e-6)

        clap_intent = pair_ratio is not None and (
            pair_ratio <= CLAP_INTENT_RATIO or approach >= CLAP_INTENT_APPROACH
        )

        if pair_ratio is not None and pair_ratio >= CLAP_ARM_RATIO:
            self.armed = True

        if (not clap_active and self.armed and now >= self.cooldown_until 
            and pair_ratio is not None and pair_ratio <= CLAP_NEAR_RATIO):
            self.latched_until = now + CLAP_LATCH_S
            self.cooldown_until = now + CLAP_COOLDOWN_S
            self.armed = False
            clap_active = True
            print(f"[{_timestamp()}] GLOBAL: Clap")

        return clap_active, clap_intent


# =============================================================================
# STRETCH DETECTION (TWO-HAND GESTURE)
# =============================================================================

@dataclass
class StretchDetector:
    """Detects stretch gestures (two pointing fingers moving apart/together)."""
    prev_dpx: float | None = None
    prev_t: float | None = None
    cumulative_px: float = 0.0

    def update(
        self, detected: list[DetectedHand], now: float, require_pointers: bool = True
    ) -> tuple[bool, float, float, float]:
        """
        Update stretch detection.
        
        Returns:
            (active, delta_px, delta_per_s, cumulative_px)
        """
        active = (len(detected) == 2 and 
                  (not require_pointers or (detected[0].pointer and detected[1].pointer)))

        if not active:
            self.prev_dpx = None
            self.prev_t = None
            self.cumulative_px = 0.0
            return False, 0.0, 0.0, 0.0

        p0 = detected[0].feats.index_tip_px
        p1 = detected[1].feats.index_tip_px
        dpx = dist2(p0, p1)

        if self.prev_dpx is None:
            self.prev_dpx = dpx
            self.prev_t = now
            return True, 0.0, 0.0, 0.0

        dt = max(now - self.prev_t, 1e-6)
        delta_px = dpx - self.prev_dpx
        delta_per_s = delta_px / dt
        self.cumulative_px += delta_px

        self.prev_dpx = dpx
        self.prev_t = now

        return True, delta_px, delta_per_s, self.cumulative_px
