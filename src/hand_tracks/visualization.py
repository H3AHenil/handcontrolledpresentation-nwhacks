"""Visualization utilities for finger-screen tracking."""

import cv2
import numpy as np
from numpy.typing import NDArray

from apriltage import (
    COLOR_GREEN,
    COLOR_MAGENTA,
    COLOR_RED,
    COLOR_YELLOW,
    COLOR_GRAY,
    FONT,
    LINE_THICKNESS,
)

from .screen_mapper import MultiScreenMapper, ScreenResult


def draw_screen_boundaries(frame: NDArray[np.uint8], mapper: MultiScreenMapper) -> None:
    """Draw boundary quadrilaterals for all detected screens."""
    for screen_idx in mapper.states:
        corners = mapper.get_screen_corners(screen_idx)
        if corners is None:
            continue

        pts = np.array([
            corners["tl"], corners["tr"], corners["br"], corners["bl"]
        ], dtype=np.int32)
        cv2.polylines(frame, [pts], True, COLOR_MAGENTA, LINE_THICKNESS)


def draw_finger_marker(
    frame: NDArray[np.uint8],
    finger_pos: tuple[int, int] | None,
    result: ScreenResult | None,
) -> None:
    """Draw finger position marker and coordinate info."""
    if finger_pos is None:
        cv2.putText(frame, "No hand detected", (10, 30), FONT, 0.7, COLOR_GRAY, 2)
        return

    fx, fy = finger_pos
    cv2.circle(frame, (fx, fy), 12, COLOR_GREEN, -1)
    cv2.circle(frame, (fx, fy), 14, (0, 0, 0), 2)

    if result:
        color = COLOR_GREEN
        text = f"Screen {result.screen_idx}: ({result.rel_x:.3f}, {result.rel_y:.3f})"
    else:
        color = COLOR_RED
        text = "Outside screen bounds"

    cv2.putText(frame, text, (10, 30), FONT, 0.8, color, 2)
    cv2.putText(frame, f"Finger: ({fx}, {fy})", (10, 60), FONT, 0.6, COLOR_GRAY, 2)


def draw_calibration_status(
    frame: NDArray[np.uint8],
    mapper: MultiScreenMapper,
    y_start: int = 90,
) -> None:
    """Draw calibration status for all screens."""
    if not mapper.states:
        cv2.putText(frame, "No AprilTags detected", (10, y_start), FONT, 0.6, COLOR_RED, 2)
        return

    for i, screen_idx in enumerate(sorted(mapper.states)):
        y = y_start + i * 25
        n = mapper.get_tag_count(screen_idx)

        if n == 4:
            color, status = COLOR_GREEN, "READY"
        elif n >= 3:
            color, status = COLOR_YELLOW, f"{n}/4 tags"
        else:
            color, status = COLOR_RED, f"{n}/4 tags"

        cv2.putText(frame, f"Screen {screen_idx}: {status}", (10, y), FONT, 0.5, color, 2)


class TrackerDisplay:
    """Manages OpenCV window and visualization."""

    def __init__(self, window_name: str = "Finger Screen Tracker"):
        self.window_name = window_name
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    def render(
        self,
        frame: NDArray[np.uint8],
        mapper: MultiScreenMapper,
        finger_pos: tuple[int, int] | None,
        screen_result: ScreenResult | None,
    ) -> None:
        """Draw all visualizations on frame."""
        draw_screen_boundaries(frame, mapper)
        draw_finger_marker(frame, finger_pos, screen_result)
        draw_calibration_status(frame, mapper)

    def show(self, frame: NDArray[np.uint8]) -> int:
        """Display frame and return key press."""
        cv2.imshow(self.window_name, frame)
        return cv2.waitKey(1) & 0xFF

    def close(self) -> None:
        """Close display window."""
        cv2.destroyWindow(self.window_name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
