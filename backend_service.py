"""
Backend Service for Gesture-to-UDP Translation.

Handles state tracking and transitions for sending gesture commands
to the Windows controller via UDP.
"""

from dataclasses import dataclass, field
from typing import Literal

from Controller.UDP import UDPGestureController
from src.hand_gestures import DetectedHand
from src.hand_tracks import ScreenResult


# Constants for gesture thresholds
STRETCH_INITIAL_DISTANCE_PX = 200.0  # Default initial distance for stretch ratio
STRETCH_ZOOM_SENSITIVITY = 0.005     # How much stretch (px) = 1 unit of zoom ratio
ROLL_SCROLL_SENSITIVITY = 3.0        # Roll degrees per scroll step


@dataclass
class GestureState:
    """Tracks previous frame state for detecting transitions."""
    prev_pinch: dict[str, bool] = field(default_factory=lambda: {"Left": False, "Right": False, "Unknown": False})
    prev_clap_active: bool = False
    prev_thumbrot: dict[str, bool] = field(default_factory=lambda: {"Left": False, "Right": False, "Unknown": False})
    prev_roll: dict[str, float | None] = field(default_factory=lambda: {"Left": None, "Right": None, "Unknown": None})
    stretch_initial_dist: float | None = None
    stretch_active: bool = False
    last_pointer_screen: int = -1
    # Track last known position per hand for fallback
    last_pos: dict[str, tuple[float, float]] = field(default_factory=lambda: {"Left": (0.5, 0.5), "Right": (0.5, 0.5), "Unknown": (0.5, 0.5)})
    last_screen_idx: dict[str, int] = field(default_factory=lambda: {"Left": -1, "Right": -1, "Unknown": -1})


class GestureBackendService:
    """
    Backend service that translates hand gestures to UDP commands.
    
    Handles:
    - State tracking for detecting gesture transitions (start/end)
    - Converting gesture data to appropriate UDP API calls
    - Managing the UDP controller lifecycle
    """

    def __init__(
        self,
        gesture_port: int = 9090,
        legacy_port: int = 8080,
        target_ip: str = "127.0.0.1",
        broadcast: bool = False,
        enabled: bool = True,
    ):
        self.enabled = enabled
        self._controller: UDPGestureController | None = None
        self._state = GestureState()
        
        if enabled:
            self._controller = UDPGestureController(
                gesture_port=gesture_port,
                legacy_port=legacy_port,
                target_ip=target_ip,
                broadcast=broadcast,
            )

    def _send_pointer(self, screen_result: ScreenResult, label: str = "Unknown") -> None:
        """Send pointer gesture for cursor movement."""
        if not self._controller:
            return
        self._controller.pointer(
            x=screen_result.rel_x,
            y=screen_result.rel_y,
            screen_index=screen_result.screen_idx,
        )
        # Track last known position for this hand
        self._state.last_pos[label] = (screen_result.rel_x, screen_result.rel_y)
        self._state.last_screen_idx[label] = screen_result.screen_idx
        self._state.last_pointer_screen = screen_result.screen_idx

    def _send_pinch(self, x: float, y: float, active: bool, screen_index: int = -1) -> None:
        """Send pinch gesture for click/drag."""
        if not self._controller:
            return
        self._controller.pinch(x=x, y=y, active=active, screen_index=screen_index)

    def _send_thumbs_up(self, roll: float) -> None:
        """Send thumbs up gesture for scrolling."""
        if not self._controller:
            return
        self._controller.thumbs_up(roll=roll)

    def _send_two_finger_zoom(self, x: float, y: float, stretch_ratio: float, screen_index: int = -1) -> None:
        """Send two-finger zoom gesture."""
        if not self._controller:
            return
        self._controller.two_finger_zoom(x=x, y=y, stretch=stretch_ratio, screen_index=screen_index)

    def _send_swipe(self, direction: Literal["left", "right", "up", "down"]) -> None:
        """Send swipe gesture."""
        if not self._controller:
            return
        self._controller.swipe(direction=direction)

    def _send_clap(self) -> None:
        """Send clap gesture to toggle mode."""
        if not self._controller:
            return
        self._controller.clap()

    def _send_no_gesture(self) -> None:
        """Send no gesture to release state."""
        if not self._controller:
            return
        self._controller.no_gesture()

    def process_frame(
        self,
        detected: list[DetectedHand],
        screen_result: ScreenResult | None,
        clap_active: bool,
        stretch_active: bool,
        stretch_cumulative: float,
        swipe_detected: bool = False,
        swipe_direction: Literal["left", "right"] | None = None,
    ) -> None:
        """
        Process a frame's gesture data and send appropriate UDP commands.
        
        Args:
            detected: List of detected hands with gesture info
            screen_result: Screen mapping result if pointer is on screen
            clap_active: Whether clap gesture is currently active
            stretch_active: Whether stretch (two-hand zoom) is active
            stretch_cumulative: Cumulative stretch distance in pixels
            swipe_detected: Whether a swipe was just detected this frame
            swipe_direction: Direction of swipe if detected
        """
        if not self.enabled:
            return

        # Handle clap transition (only send once when clap starts)
        if clap_active and not self._state.prev_clap_active:
            self._send_clap()
        self._state.prev_clap_active = clap_active

        # Handle swipe (already a discrete event)
        if swipe_detected and swipe_direction:
            self._send_swipe(swipe_direction)

        # Handle stretch (two-hand zoom)
        if stretch_active and len(detected) >= 2:
            self._handle_stretch(detected, stretch_cumulative)
        elif self._state.stretch_active and not stretch_active:
            # Stretch ended, reset initial distance
            self._state.stretch_initial_dist = None
            self._state.stretch_active = False
        
        # Process individual hands
        for d in detected:
            self._process_hand(d, screen_result)

        # Handle no hands case
        if not detected:
            self._handle_no_hands()

    def _handle_stretch(self, detected: list[DetectedHand], stretch_cumulative: float) -> None:
        """Handle two-hand stretch/zoom gesture."""
        if not self._state.stretch_active:
            # Starting stretch - record initial state
            self._state.stretch_active = True
            self._state.stretch_initial_dist = STRETCH_INITIAL_DISTANCE_PX
        
        # Calculate stretch ratio (1.0 = no change, >1.0 = zoom in, <1.0 = zoom out)
        stretch_ratio = 1.0 + (stretch_cumulative * STRETCH_ZOOM_SENSITIVITY)
        stretch_ratio = max(0.1, min(5.0, stretch_ratio))  # Clamp to reasonable range
        
        # Get center point between the two fingers
        p0 = detected[0].feats.index_tip_px
        p1 = detected[1].feats.index_tip_px
        center_x = (p0[0] + p1[0]) / 2
        center_y = (p0[1] + p1[1]) / 2
        
        # Normalize to [0, 1] - assuming some frame size, will be approximate
        # In practice, we'd need the actual screen result for accurate positioning
        norm_x = max(0.0, min(1.0, center_x / 1280))  # Assuming 1280 width
        norm_y = max(0.0, min(1.0, center_y / 720))   # Assuming 720 height
        
        self._send_two_finger_zoom(norm_x, norm_y, stretch_ratio, screen_index=-1)

    def _process_hand(self, d: DetectedHand, screen_result: ScreenResult | None) -> None:
        """Process a single hand's gestures."""
        label = d.label
        
        # Handle pointer mode - send cursor position and update last known position
        if d.pointer and screen_result:
            self._send_pointer(screen_result, label)
        
        # Get position to use (current screen_result or last known position)
        if screen_result:
            pos_x, pos_y = screen_result.rel_x, screen_result.rel_y
            screen_idx = screen_result.screen_idx
            # Update last known position
            self._state.last_pos[label] = (pos_x, pos_y)
            self._state.last_screen_idx[label] = screen_idx
        else:
            # Use last known position as fallback
            pos_x, pos_y = self._state.last_pos.get(label, (0.5, 0.5))
            screen_idx = self._state.last_screen_idx.get(label, -1)
        
        # Handle pinch transitions
        prev_pinch = self._state.prev_pinch.get(label, False)
        if d.pinch and not prev_pinch:
            # Pinch started - send mouse down at current/last known position
            self._send_pinch(pos_x, pos_y, active=True, screen_index=screen_idx)
        elif not d.pinch and prev_pinch:
            # Pinch ended - send mouse up
            self._send_pinch(pos_x, pos_y, active=False, screen_index=screen_idx)
        self._state.prev_pinch[label] = d.pinch
        
        # Handle thumbrot (hand rotation for scrolling)
        if d.thumbrot and d.roll is not None:
            prev_roll = self._state.prev_roll.get(label)
            if prev_roll is not None:
                # Send continuous roll value for scrolling
                self._send_thumbs_up(d.roll)
            self._state.prev_roll[label] = d.roll
            self._state.prev_thumbrot[label] = True
        elif self._state.prev_thumbrot.get(label, False):
            # Thumbrot ended
            self._state.prev_roll[label] = None
            self._state.prev_thumbrot[label] = False

    def _handle_no_hands(self) -> None:
        """Handle case when no hands are detected."""
        # Check if any pinch was active and release it at last known position
        for label in ["Left", "Right", "Unknown"]:
            if self._state.prev_pinch.get(label, False):
                pos_x, pos_y = self._state.last_pos.get(label, (0.5, 0.5))
                screen_idx = self._state.last_screen_idx.get(label, -1)
                self._send_pinch(pos_x, pos_y, active=False, screen_index=screen_idx)
                self._state.prev_pinch[label] = False
        
        # Reset thumbrot state
        for label in ["Left", "Right", "Unknown"]:
            self._state.prev_roll[label] = None
            self._state.prev_thumbrot[label] = False
        
        # Reset stretch state
        if self._state.stretch_active:
            self._state.stretch_active = False
            self._state.stretch_initial_dist = None

    def close(self) -> None:
        """Close the UDP controller."""
        if self._controller:
            self._controller.close()
            self._controller = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
