"""
Test suite for UDP Gesture Controller

Run with: python -m pytest test_UDP.py -v
Or simply: python test_UDP.py
"""

import unittest
from unittest.mock import MagicMock, patch
import json
import socket

from UDP import UDPGestureController, UDPRemoteController


class TestUDPGestureController(unittest.TestCase):
    """Test cases for UDPGestureController class."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the socket to avoid actual network operations
        self.mock_socket = MagicMock(spec=socket.socket)
        self.socket_patcher = patch('socket.socket', return_value=self.mock_socket)
        self.socket_patcher.start()
        self.controller = UDPGestureController()

    def tearDown(self):
        """Clean up after tests."""
        self.controller.close()
        self.socket_patcher.stop()

    # ============================================================
    # Initialization Tests
    # ============================================================

    def test_default_initialization(self):
        """Test default initialization values."""
        self.assertEqual(self.controller.gesture_port, 9090)
        self.assertEqual(self.controller.legacy_port, 8080)
        self.assertEqual(self.controller.target_ip, "127.0.0.1")

    def test_custom_ports(self):
        """Test initialization with custom ports."""
        controller = UDPGestureController(gesture_port=9999, legacy_port=8888)
        self.assertEqual(controller.gesture_port, 9999)
        self.assertEqual(controller.legacy_port, 8888)
        controller.close()

    def test_broadcast_mode(self):
        """Test broadcast mode initialization."""
        controller = UDPGestureController(broadcast=True)
        self.assertEqual(controller.target_ip, "255.255.255.255")
        self.mock_socket.setsockopt.assert_called_with(
            socket.SOL_SOCKET, socket.SO_BROADCAST, 1
        )
        controller.close()

    def test_custom_target_ip(self):
        """Test custom target IP address."""
        controller = UDPGestureController(target_ip="192.168.1.100")
        self.assertEqual(controller.target_ip, "192.168.1.100")
        controller.close()

    def test_context_manager(self):
        """Test context manager usage."""
        with UDPGestureController() as ctrl:
            self.assertIsInstance(ctrl, UDPGestureController)
        self.mock_socket.close.assert_called()

    def test_backward_compatibility_alias(self):
        """Test that UDPRemoteController is an alias."""
        self.assertIs(UDPRemoteController, UDPGestureController)

    # ============================================================
    # Gesture API Tests (JSON Protocol)
    # ============================================================

    def test_pointer_gesture(self):
        """Test pointer gesture sends correct JSON."""
        self.controller.pointer(0.5, 0.7, screen_index=1, confidence=0.9)

        self._assert_json_sent({
            "type": "pointer",
            "x": 0.5,
            "y": 0.7,
            "fingerCount": 1,
            "screenIndex": 1,
            "confidence": 0.9
        }, port=9090)

    def test_pointer_gesture_defaults(self):
        """Test pointer gesture with default values."""
        self.controller.pointer(0.3, 0.4)

        self._assert_json_sent({
            "type": "pointer",
            "x": 0.3,
            "y": 0.4,
            "fingerCount": 1,
            "screenIndex": -1,
            "confidence": 0.95
        }, port=9090)

    def test_two_finger_zoom(self):
        """Test two-finger zoom gesture."""
        self.controller.two_finger_zoom(0.5, 0.5, stretch=1.5, screen_index=0, confidence=0.85)

        self._assert_json_sent({
            "type": "two_finger",
            "x": 0.5,
            "y": 0.5,
            "fingerCount": 2,
            "screenIndex": 0,
            "stretch": 1.5,
            "confidence": 0.85
        }, port=9090)

    def test_swipe_right(self):
        """Test swipe right gesture."""
        self.controller.swipe("right")

        self._assert_json_sent({
            "type": "swipe",
            "swipeDirection": "right",
            "confidence": 0.95
        }, port=9090)

    def test_swipe_left(self):
        """Test swipe left gesture."""
        self.controller.swipe("left", confidence=0.8)

        self._assert_json_sent({
            "type": "swipe",
            "swipeDirection": "left",
            "confidence": 0.8
        }, port=9090)

    def test_swipe_up(self):
        """Test swipe up gesture."""
        self.controller.swipe("up")

        self._assert_json_sent({
            "type": "swipe",
            "swipeDirection": "up",
            "confidence": 0.95
        }, port=9090)

    def test_swipe_down(self):
        """Test swipe down gesture."""
        self.controller.swipe("down")

        self._assert_json_sent({
            "type": "swipe",
            "swipeDirection": "down",
            "confidence": 0.95
        }, port=9090)

    def test_pinch_active(self):
        """Test pinch gesture with active=True (mouse down)."""
        self.controller.pinch(0.3, 0.4, active=True, screen_index=0)

        self._assert_json_sent({
            "type": "pinch",
            "x": 0.3,
            "y": 0.4,
            "screenIndex": 0,
            "pinchActive": True,
            "confidence": 0.95
        }, port=9090)

    def test_pinch_inactive(self):
        """Test pinch gesture with active=False (mouse up)."""
        self.controller.pinch(0.7, 0.8, active=False)

        self._assert_json_sent({
            "type": "pinch",
            "x": 0.7,
            "y": 0.8,
            "screenIndex": -1,
            "pinchActive": False,
            "confidence": 0.95
        }, port=9090)

    def test_thumbs_up(self):
        """Test thumbs up gesture."""
        self.controller.thumbs_up(roll=-5.0, confidence=0.92)

        self._assert_json_sent({
            "type": "thumbs_up",
            "roll": -5.0,
            "confidence": 0.92
        }, port=9090)

    def test_clap(self):
        """Test clap gesture."""
        self.controller.clap(confidence=0.88)

        self._assert_json_sent({
            "type": "clap",
            "confidence": 0.88
        }, port=9090)

    def test_no_gesture(self):
        """Test no gesture signal."""
        self.controller.no_gesture()

        self._assert_json_sent({"type": "none"}, port=9090)

    # ============================================================
    # Legacy API Tests (Text Protocol)
    # ============================================================

    def test_left_click(self):
        """Test left click command."""
        self.controller.left_click()
        self._assert_text_sent("LeftClick", port=8080)

    def test_right_click(self):
        """Test right click command."""
        self.controller.right_click()
        self._assert_text_sent("RightClick", port=8080)

    def test_move_relative(self):
        """Test relative move command."""
        self.controller.move_relative(10, -5)
        self._assert_text_sent("Move:10,-5", port=8080)

    def test_move_absolute(self):
        """Test absolute move command."""
        self.controller.move_absolute(0, 960, 540)
        self._assert_text_sent("Abs:0,960,540", port=8080)

    def test_scroll_up(self):
        """Test scroll up command."""
        self.controller.scroll(120)
        self._assert_text_sent("Scroll:120", port=8080)

    def test_scroll_down(self):
        """Test scroll down command."""
        self.controller.scroll(-120)
        self._assert_text_sent("Scroll:-120", port=8080)

    def test_zoom_positive(self):
        """Test zoom in command."""
        self.controller.zoom(2)
        self._assert_text_sent("Zoom:2", port=8080)

    def test_zoom_negative(self):
        """Test zoom out command."""
        self.controller.zoom(-3)
        self._assert_text_sent("Zoom:-3", port=8080)

    def test_zoom_in(self):
        """Test zoom_in convenience method."""
        self.controller.zoom_in(2)
        self._assert_text_sent("Zoom:2", port=8080)

    def test_zoom_out(self):
        """Test zoom_out convenience method."""
        self.controller.zoom_out(2)
        self._assert_text_sent("Zoom:-2", port=8080)

    def test_legacy_pinch_out(self):
        """Test legacy pinch out (zoom in) command."""
        self.controller.legacy_pinch("out", 2)
        self._assert_text_sent("Pinch:1,2", port=8080)

    def test_legacy_pinch_in(self):
        """Test legacy pinch in (zoom out) command."""
        self.controller.legacy_pinch("in", 3)
        self._assert_text_sent("Pinch:-1,3", port=8080)

    def test_pinch_in_convenience(self):
        """Test pinch_in convenience method."""
        self.controller.pinch_in(2)
        self._assert_text_sent("Pinch:-1,2", port=8080)

    def test_pinch_out_convenience(self):
        """Test pinch_out convenience method."""
        self.controller.pinch_out(3)
        self._assert_text_sent("Pinch:1,3", port=8080)

    def test_send_raw(self):
        """Test sending raw command."""
        self.controller.send_raw("CustomCommand:arg1,arg2")
        self._assert_text_sent("CustomCommand:arg1,arg2", port=8080)

    # ============================================================
    # Helper Methods
    # ============================================================

    def _assert_json_sent(self, expected_data: dict, port: int):
        """Assert that the correct JSON was sent via UDP."""
        self.mock_socket.sendto.assert_called()
        call_args = self.mock_socket.sendto.call_args
        sent_data = call_args[0][0].decode('utf-8')
        sent_addr = call_args[0][1]

        self.assertEqual(json.loads(sent_data), expected_data)
        self.assertEqual(sent_addr, ("127.0.0.1", port))

    def _assert_text_sent(self, expected_text: str, port: int):
        """Assert that the correct text was sent via UDP."""
        self.mock_socket.sendto.assert_called()
        call_args = self.mock_socket.sendto.call_args
        sent_data = call_args[0][0].decode('utf-8')
        sent_addr = call_args[0][1]

        self.assertEqual(sent_data, expected_text)
        self.assertEqual(sent_addr, ("127.0.0.1", port))


class TestUDPGestureControllerIntegration(unittest.TestCase):
    """Integration tests (requires actual socket, but doesn't require receiver)."""

    def test_socket_creation(self):
        """Test that real socket can be created."""
        controller = UDPGestureController()
        self.assertIsNotNone(controller.sock)
        self.assertEqual(controller.sock.type, socket.SOCK_DGRAM)
        controller.close()


if __name__ == '__main__':
    print("=" * 60)
    print("UDP Gesture Controller Test Suite")
    print("=" * 60)

    # Run tests
    unittest.main(verbosity=2)

