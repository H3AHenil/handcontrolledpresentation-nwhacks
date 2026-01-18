"""
UDP Gesture Controller Python Interface

This module provides a Python interface for sending gesture data to the C# GestureController
via UDP. It supports both the legacy text-based protocol and the new JSON-based gesture protocol.

Usage:
    from UDP import UDPGestureController

    with UDPGestureController() as controller:
        controller.pointer(0.5, 0.5)  # Move cursor to center
        controller.zoom(1.5)          # Zoom in
        controller.swipe("right")     # Swipe right
"""

import socket
import json
from typing import Literal, Optional


class UDPGestureController:
    """UDP Gesture Controller for sending gesture commands over UDP."""

    # Default ports
    LEGACY_PORT = 8080       # Legacy text-based protocol
    GESTURE_PORT = 9090      # JSON-based gesture protocol

    def __init__(
        self,
        gesture_port: int = GESTURE_PORT,
        legacy_port: int = LEGACY_PORT,
        target_ip: str = "127.0.0.1",
        broadcast: bool = False
    ):
        """
        Initialize the UDP Gesture Controller.

        Args:
            gesture_port: Port for JSON gesture protocol (default: 9090)
            legacy_port: Port for legacy text protocol (default: 8080)
            target_ip: Target IP address (default: 127.0.0.1)
            broadcast: If True, use broadcast mode (255.255.255.255)
        """
        self.gesture_port = gesture_port
        self.legacy_port = legacy_port
        self.target_ip = "255.255.255.255" if broadcast else target_ip

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if broadcast:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def _send_json(self, data: dict, port: Optional[int] = None):
        """Send JSON data over UDP."""
        # Convert numpy types to native Python types for JSON serialization
        sanitized = self._sanitize_for_json(data)
        json_data = json.dumps(sanitized)
        target_port = port or self.gesture_port
        self.sock.sendto(json_data.encode('utf-8'), (self.target_ip, target_port))

    def _sanitize_for_json(self, obj):
        """
        Recursively convert numpy types to native Python types for JSON serialization.

        Args:
            obj: Object to sanitize (dict, list, or scalar value)

        Returns:
            JSON-serializable object with numpy types converted to Python types
        """
        if isinstance(obj, dict):
            return {k: self._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._sanitize_for_json(item) for item in obj]
        elif hasattr(obj, 'item'):
            # numpy scalar types have .item() method to convert to Python scalar
            return obj.item()
        elif isinstance(obj, float):
            return float(obj)
        elif isinstance(obj, int):
            return int(obj)
        else:
            return obj

    def _send_text(self, command: str, port: Optional[int] = None):
        """Send text command over UDP (legacy protocol)."""
        target_port = port or self.legacy_port
        self.sock.sendto(command.encode('utf-8'), (self.target_ip, target_port))

    # ============================================================
    # GESTURE API (JSON Protocol - Port 9090)
    # ============================================================

    def pointer(
        self,
        x: float,
        y: float,
        screen_index: int = -1,
        confidence: float = 0.95
    ):
        """
        Send a single-finger pointer gesture to move the cursor.

        Args:
            x: Normalized X position [0, 1] where 0=left, 1=right
            y: Normalized Y position [0, 1] where 0=top, 1=bottom
            screen_index: Target screen index (0-based). -1 = use configured default.
            confidence: Detection confidence [0, 1]
        """
        self._send_json({
            "type": "pointer",
            "x": x,
            "y": y,
            "fingerCount": 1,
            "screenIndex": screen_index,
            "confidence": confidence
        })

    def two_finger_zoom(
        self,
        x: float,
        y: float,
        stretch: float,
        screen_index: int = -1,
        confidence: float = 0.95
    ):
        """
        Send a two-finger zoom gesture (triggers Ctrl+MouseWheel zoom).

        Args:
            x: Center X position of the two fingers [0, 1]
            y: Center Y position of the two fingers [0, 1]
            stretch: Cumulative stretch value (ratio of current to initial distance)
                     > 1.0 = zoom in (fingers spreading)
                     < 1.0 = zoom out (fingers pinching)
            screen_index: Target screen index (0-based). -1 = use configured default.
            confidence: Detection confidence [0, 1]
        """
        self._send_json({
            "type": "two_finger",
            "x": x,
            "y": y,
            "fingerCount": 2,
            "screenIndex": screen_index,
            "stretch": stretch,
            "confidence": confidence
        })

    def swipe(
        self,
        direction: Literal["left", "right", "up", "down"],
        confidence: float = 0.95
    ):
        """
        Send a swipe gesture (triggers Alt+Tab or Win+Tab).

        Args:
            direction: One of "left", "right", "up", "down"
                       - "right": Alt+Tab (next window)
                       - "left": Shift+Alt+Tab (previous window)
                       - "up": Win+Tab (task view)
                       - "down": reserved
            confidence: Detection confidence [0, 1]
        """
        self._send_json({
            "type": "swipe",
            "swipeDirection": direction,
            "confidence": confidence
        })

    def pinch(
        self,
        x: float,
        y: float,
        active: bool,
        screen_index: int = -1,
        confidence: float = 0.95
    ):
        """
        Send a pinch/grab gesture (starts/ends a click-and-hold for drag operations).

        Args:
            x: Position X [0, 1]
            y: Position Y [0, 1]
            active: True = mouse down (start drag), False = mouse up (end drag)
            screen_index: Target screen index (0-based). -1 = use configured default.
            confidence: Detection confidence [0, 1]
        """
        self._send_json({
            "type": "pinch",
            "x": x,
            "y": y,
            "screenIndex": screen_index,
            "pinchActive": active,
            "confidence": confidence
        })

    def thumbs_up(self, roll: float, confidence: float = 0.95):
        """
        Send a thumbs up gesture with roll for vertical scrolling.

        Args:
            roll: Roll angle/value. Positive = scroll up, Negative = scroll down.
                  The controller accumulates changes and converts to wheel events.
            confidence: Detection confidence [0, 1]
        """
        self._send_json({
            "type": "thumbs_up",
            "roll": roll,
            "confidence": confidence
        })

    def clap(self, confidence: float = 0.95):
        """
        Send a clap gesture to toggle between Cursor and Laser Pointer modes.

        Args:
            confidence: Detection confidence [0, 1]
        """
        self._send_json({
            "type": "clap",
            "confidence": confidence
        })

    def no_gesture(self):
        """Send a 'no gesture' signal to release any active pinch or gesture state."""
        self._send_json({"type": "none"})

    # ============================================================
    # LEGACY API (Text Protocol - Port 8080)
    # ============================================================

    def left_click(self):
        """Perform a left mouse click (legacy protocol)."""
        self._send_text("LeftClick")

    def right_click(self):
        """Perform a right mouse click (legacy protocol)."""
        self._send_text("RightClick")

    def move_relative(self, dx: int, dy: int):
        """
        Move the cursor by a relative offset (legacy protocol).

        Args:
            dx: Horizontal offset in pixels (positive = right)
            dy: Vertical offset in pixels (positive = down)
        """
        self._send_text(f"Move:{dx},{dy}")

    def move_absolute(self, screen: int, x: int, y: int):
        """
        Move the cursor to an absolute position on a specific screen (legacy protocol).

        Args:
            screen: Target screen index (0-based)
            x: X coordinate in pixels on the target screen
            y: Y coordinate in pixels on the target screen
        """
        self._send_text(f"Abs:{screen},{x},{y}")

    def scroll(self, delta: int):
        """
        Perform a scroll action (legacy protocol).

        Args:
            delta: Scroll amount. Positive = scroll up, Negative = scroll down.
                   Typical values: 120 (one notch up), -120 (one notch down)
        """
        self._send_text(f"Scroll:{delta}")

    def zoom(self, steps: int):
        """
        Perform a zoom action using Ctrl+Wheel (legacy protocol).

        Args:
            steps: Zoom steps. Positive = zoom in, Negative = zoom out.
        """
        self._send_text(f"Zoom:{steps}")

    def zoom_in(self, steps: int = 1):
        """Zoom in by the specified number of steps (legacy protocol)."""
        self.zoom(steps)

    def zoom_out(self, steps: int = 1):
        """Zoom out by the specified number of steps (legacy protocol)."""
        self.zoom(-steps)

    def legacy_pinch(self, direction: Literal["in", "out"], steps: int):
        """
        Perform a pinch gesture zoom (legacy protocol).

        Args:
            direction: "in" = zoom out (pinch in), "out" = zoom in (pinch out)
            steps: Intensity/steps (larger value = more zoom)
        """
        dir_value = 1 if direction == "out" else -1
        self._send_text(f"Pinch:{dir_value},{steps}")

    def pinch_in(self, steps: int = 1):
        """Pinch in to zoom out (legacy protocol)."""
        self.legacy_pinch("in", steps)

    def pinch_out(self, steps: int = 1):
        """Pinch out to zoom in (legacy protocol)."""
        self.legacy_pinch("out", steps)

    def send_raw(self, command: str):
        """
        Send a raw command string (legacy protocol).

        Args:
            command: Raw protocol command string
        """
        self._send_text(command)

    def close(self):
        """Close the UDP socket."""
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Backward compatibility alias
UDPRemoteController = UDPGestureController

