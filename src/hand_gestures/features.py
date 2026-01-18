"""Hand feature extraction from MediaPipe landmarks."""

import math
from dataclasses import dataclass

from .math_utils import (
    Point2, Point3, Vec3,
    dist3, mean_point2, mean_point3, normalize3, sub3, angle_3pt_deg,
)
from .config import (
    EXT_MIN_PIP_ANGLE_DEG, FINGER_EXT_TIP_RATIO_3,
    CURL_MAX_PIP_ANGLE_DEG, FINGER_CURLED_TIP_RATIO_3,
    THUMB_MIN_IP_ANGLE_DEG, THUMB_TIP_RATIO_3,
    INVERT_HANDEDNESS,
)


# MediaPipe landmark indices
class LM:
    WRIST = 0
    THUMB_MCP, THUMB_IP, THUMB_TIP = 2, 3, 4
    INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
    MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
    RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
    PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20


@dataclass
class HandFeatures:
    """Extracted features from hand landmarks."""
    hand_scale_3: float
    palm_center_3: Point3
    palm_center_px: Point2
    flick_angle_deg: float

    wrist_3: Point3
    index_mcp_3: Point3
    pinky_mcp_3: Point3
    middle_mcp_3: Point3

    index_tip_px: Point2
    middle_tip_px: Point2
    index_tip_3: Point3
    thumb_tip_3: Point3

    index_ext: bool
    middle_ext: bool
    ring_ext: bool
    pinky_ext: bool

    index_curled: bool
    middle_curled: bool
    ring_curled: bool
    pinky_curled: bool

    thumb_vec_u: Vec3
    thumb_strong: bool

    @property
    def curled_count(self) -> int:
        return sum([self.index_curled, self.middle_curled, self.ring_curled, self.pinky_curled])


def _is_extended(pip_angle: float, tip_ratio: float) -> bool:
    """Check if finger is extended based on PIP angle and tip distance ratio."""
    return pip_angle >= EXT_MIN_PIP_ANGLE_DEG and tip_ratio >= FINGER_EXT_TIP_RATIO_3


def _is_curled(pip_angle: float, tip_ratio: float) -> bool:
    """Check if finger is curled based on PIP angle and tip distance ratio."""
    return pip_angle <= CURL_MAX_PIP_ANGLE_DEG or tip_ratio <= FINGER_CURLED_TIP_RATIO_3


def extract_features(px: list[Point2], n3: list[Point3]) -> HandFeatures:
    """
    Extract hand features from pixel and normalized 3D landmarks.
    
    Args:
        px: List of 21 (x, y) pixel coordinates
        n3: List of 21 normalized (x, y, z) coordinates
    
    Returns:
        HandFeatures dataclass with all extracted features
    """
    hand_scale_3 = max(dist3(n3[LM.INDEX_MCP], n3[LM.PINKY_MCP]), 1e-3)
    
    palm_center_3 = mean_point3([
        n3[LM.WRIST], n3[LM.INDEX_MCP], n3[LM.MIDDLE_MCP], n3[LM.PINKY_MCP]
    ])
    palm_center_px = mean_point2([
        px[LM.WRIST], px[LM.INDEX_MCP], px[LM.MIDDLE_MCP], px[LM.PINKY_MCP]
    ])

    def tip_ratio(tip_idx: int) -> float:
        return dist3(n3[tip_idx], palm_center_3) / (hand_scale_3 + 1e-9)

    # Finger PIP angles
    idx_ang = angle_3pt_deg(n3[LM.INDEX_MCP], n3[LM.INDEX_PIP], n3[LM.INDEX_DIP])
    mid_ang = angle_3pt_deg(n3[LM.MIDDLE_MCP], n3[LM.MIDDLE_PIP], n3[LM.MIDDLE_DIP])
    rng_ang = angle_3pt_deg(n3[LM.RING_MCP], n3[LM.RING_PIP], n3[LM.RING_DIP])
    pky_ang = angle_3pt_deg(n3[LM.PINKY_MCP], n3[LM.PINKY_PIP], n3[LM.PINKY_DIP])
    th_ang = angle_3pt_deg(n3[LM.THUMB_MCP], n3[LM.THUMB_IP], n3[LM.THUMB_TIP])

    # Tip ratios
    idx_tip_r = tip_ratio(LM.INDEX_TIP)
    mid_tip_r = tip_ratio(LM.MIDDLE_TIP)
    rng_tip_r = tip_ratio(LM.RING_TIP)
    pky_tip_r = tip_ratio(LM.PINKY_TIP)
    th_tip_r = tip_ratio(LM.THUMB_TIP)

    # Thumb vector and strength
    thumb_vec = normalize3(sub3(n3[LM.THUMB_TIP], n3[LM.THUMB_MCP]))
    thumb_strong = th_ang >= THUMB_MIN_IP_ANGLE_DEG and th_tip_r >= THUMB_TIP_RATIO_3

    # Flick angle (wrist to middle MCP direction)
    wx, wy = px[LM.WRIST]
    mx, my = px[LM.MIDDLE_MCP]
    flick_angle_deg = math.degrees(math.atan2(my - wy, mx - wx))

    return HandFeatures(
        hand_scale_3=hand_scale_3,
        palm_center_3=palm_center_3,
        palm_center_px=palm_center_px,
        flick_angle_deg=flick_angle_deg,
        wrist_3=n3[LM.WRIST],
        index_mcp_3=n3[LM.INDEX_MCP],
        pinky_mcp_3=n3[LM.PINKY_MCP],
        middle_mcp_3=n3[LM.MIDDLE_MCP],
        index_tip_px=px[LM.INDEX_TIP],
        middle_tip_px=px[LM.MIDDLE_TIP],
        index_tip_3=n3[LM.INDEX_TIP],
        thumb_tip_3=n3[LM.THUMB_TIP],
        index_ext=_is_extended(idx_ang, idx_tip_r),
        middle_ext=_is_extended(mid_ang, mid_tip_r),
        ring_ext=_is_extended(rng_ang, rng_tip_r),
        pinky_ext=_is_extended(pky_ang, pky_tip_r),
        index_curled=_is_curled(idx_ang, idx_tip_r),
        middle_curled=_is_curled(mid_ang, mid_tip_r),
        ring_curled=_is_curled(rng_ang, rng_tip_r),
        pinky_curled=_is_curled(pky_ang, pky_tip_r),
        thumb_vec_u=thumb_vec,
        thumb_strong=thumb_strong,
    )


def get_handedness_label(handedness) -> str:
    """Extract handedness label, optionally inverting left/right."""
    try:
        lbl = handedness.classification[0].label
    except Exception:
        return "Unknown"
    
    if INVERT_HANDEDNESS:
        return {"Left": "Right", "Right": "Left"}.get(lbl, lbl)
    return lbl


def hand_orientation_angles(
    wrist: Point3, index_mcp: Point3, pinky_mcp: Point3, middle_mcp: Point3
) -> tuple[float, float, float]:
    """
    Compute hand orientation as yaw, pitch, roll angles.
    
    Returns:
        (yaw, pitch, roll) in degrees
    """
    from .math_utils import cross3, yaw_pitch_from_vec
    
    across = normalize3(sub3(index_mcp, pinky_mcp))
    forward = normalize3(sub3(middle_mcp, wrist))
    
    yaw, pitch = yaw_pitch_from_vec(forward[0], forward[1], forward[2])
    
    roll = math.degrees(math.atan2(across[1], across[0]))
    if roll > 180:
        roll -= 360
    elif roll < -180:
        roll += 360
    
    return yaw, pitch, roll
