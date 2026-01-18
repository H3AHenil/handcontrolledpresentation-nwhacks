"""Finger-to-screen coordinate mapping using AprilTag homography."""

from dataclasses import dataclass

from apriltage import (
    MapperState,
    create_detector,
    create_mapper,
    detect_tags,
    detect_screens,
    update_mapper,
    camera_to_ratio,
    is_calibrated,
    get_screen_corners,
)


@dataclass
class ScreenResult:
    """Result of finger-to-screen mapping."""
    screen_idx: int
    rel_x: float
    rel_y: float

    @property
    def coords(self) -> tuple[float, float]:
        return self.rel_x, self.rel_y


class MultiScreenMapper:
    """Manages AprilTag detection and screen coordinate mapping."""

    def __init__(self):
        self._detector = create_detector()
        self._states: dict[int, MapperState] = {}
        self._last_detection = None

    @property
    def states(self) -> dict[int, MapperState]:
        """Access to screen states for visualization."""
        return self._states

    def update(self, frame) -> None:
        """Detect AprilTags and update screen mappers."""
        self._last_detection = detect_tags(self._detector, frame)
        visible_screens = detect_screens(list(self._last_detection["tag_corners"].keys()))

        for screen_idx in visible_screens:
            if screen_idx not in self._states:
                self._states[screen_idx] = create_mapper(screen_index=screen_idx)

        for state in self._states.values():
            update_mapper(state, self._last_detection["tag_corners"])

    def find_screen(self, x: int, y: int) -> ScreenResult | None:
        """
        Find which screen contains the given camera coordinates.
        
        Returns:
            ScreenResult with screen index and relative coords, or None
        """
        for screen_idx, state in self._states.items():
            if not is_calibrated(state):
                continue
            result = camera_to_ratio(state, x, y)
            if result:
                rx, ry = result
                if 0 <= rx <= 1 and 0 <= ry <= 1:
                    return ScreenResult(screen_idx, rx, ry)
        return None

    def get_screen_corners(self, screen_idx: int) -> dict | None:
        """Get corner coordinates for a screen."""
        if screen_idx not in self._states:
            return None
        return get_screen_corners(self._states[screen_idx])

    def is_screen_calibrated(self, screen_idx: int) -> bool:
        """Check if a screen is fully calibrated."""
        if screen_idx not in self._states:
            return False
        return is_calibrated(self._states[screen_idx])

    def get_tag_count(self, screen_idx: int) -> int:
        """Get number of detected tags for a screen."""
        if screen_idx not in self._states:
            return 0
        return self._states[screen_idx]["num_tags_detected"]
