"""Configuration constants for hand gesture detection."""

from enum import Enum


class ViewMode(Enum):
    FPV_BEHIND_HANDS = "FPV_BEHIND_HANDS"
    SELFIE_WEBCAM = "SELFIE_WEBCAM"


# =============================================================================
# CAMERA / VIEW SETTINGS
# =============================================================================
VIEW_MODE = ViewMode.FPV_BEHIND_HANDS
FORCE_MIRROR_INPUT = False
INVERT_HANDEDNESS = True
MAX_NUM_HANDS = 2

# Derived flip settings
DISPLAY_FLIP = VIEW_MODE == ViewMode.SELFIE_WEBCAM
PROCESS_FLIP = VIEW_MODE == ViewMode.SELFIE_WEBCAM

if FORCE_MIRROR_INPUT:
    DISPLAY_FLIP = not DISPLAY_FLIP
    PROCESS_FLIP = not PROCESS_FLIP


# =============================================================================
# TIMING / LATCHING
# =============================================================================
PINCH_LATCH_S = 0.30
CLAP_LATCH_S = 0.65
TWO_FINGER_SWIPE_LATCH_S = 0.45
CLAP_COOLDOWN_S = 0.70
LAST_SEEN_WINDOW_S = 0.30


# =============================================================================
# PINCH DETECTION
# =============================================================================
PINCH_ON = 0.62
PINCH_OFF = 0.80
PINCH_STILL_LOG_INTERVAL_S = 0.35


# =============================================================================
# FINGER EXTENSION / CURL THRESHOLDS
# =============================================================================
EXT_MIN_PIP_ANGLE_DEG = 158.0
FINGER_EXT_TIP_RATIO_3 = 0.90
CURL_MAX_PIP_ANGLE_DEG = 152.0
FINGER_CURLED_TIP_RATIO_3 = 0.84

POINTER_REQUIRE_ONLY_INDEX = True


# =============================================================================
# THUMBS UP / HAND ROTATION
# =============================================================================
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


# =============================================================================
# CLAP DETECTION
# =============================================================================
CLAP_ARM_RATIO = 1.90
CLAP_NEAR_RATIO = 0.78
CLAP_INTENT_RATIO = 1.35
CLAP_INTENT_APPROACH = 1.4


# =============================================================================
# TWO FINGER SWIPE
# =============================================================================
TFS_WINDOW_S = 0.30
TFS_MIN_PEAK_SPEED_PX_S = 900
TFS_MIN_PEAK_DIST_PX = 90
TFS_COOLDOWN_S = 0.55
TFS_DIR_CONSISTENCY_MIN = 0.55
TFS_MIN_ANGLE_DELTA_DEG = 10.0
TFS_MIN_ANGLE_SPEED_DEG_S = 80.0
TFS_STRONG_DIST_PX = 180
TFS_STRONG_SPEED_PX_S = 1600


# =============================================================================
# STRETCH GESTURE
# =============================================================================
STRETCH_REQUIRE_POINTERS = True
