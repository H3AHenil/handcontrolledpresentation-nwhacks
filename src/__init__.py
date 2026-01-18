"""Hand gesture recognition and tracking package."""

from .hand_gestures import (
    ViewMode,
    HandFeatures,
    extract_features,
    get_handedness_label,
    HandState,
    DetectedHand,
    ClapDetector,
    StretchDetector,
    is_pointer,
    is_two_finger_pose,
)

from .hand_tracks import (
    HandTracker,
    MultiScreenMapper,
    ScreenResult,
    TrackerDisplay,
)

__all__ = [
    # Gestures
    "ViewMode",
    "HandFeatures",
    "extract_features",
    "get_handedness_label",
    "HandState",
    "DetectedHand",
    "ClapDetector",
    "StretchDetector",
    "is_pointer",
    "is_two_finger_pose",
    # Tracking
    "HandTracker",
    "MultiScreenMapper",
    "ScreenResult",
    "TrackerDisplay",
]
