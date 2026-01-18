"""
Example Python script demonstrating how to send gesture data to the C# GestureController.
This shows the JSON protocol format expected by GestureUdpReceiver.

Usage:
    pip install opencv-python mediapipe
    python gesture_sender_example.py
"""

import socket
import json
import time
import math

# UDP Configuration
UDP_IP = "127.0.0.1"
UDP_PORT = 9090

def create_udp_socket():
    """Create a UDP socket for sending gesture data."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return sock

def send_gesture(sock, gesture_data: dict):
    """Send gesture data as JSON over UDP."""
    json_data = json.dumps(gesture_data)
    sock.sendto(json_data.encode('utf-8'), (UDP_IP, UDP_PORT))

# ============================================================
# GESTURE DATA TEMPLATES
# ============================================================

def pointer_gesture(x: float, y: float, screen_index: int = -1, confidence: float = 0.95) -> dict:
    """
    Single finger pointer gesture - moves the cursor.
    
    Args:
        x: Normalized X position [0, 1] where 0=left, 1=right
        y: Normalized Y position [0, 1] where 0=top, 1=bottom
        screen_index: Target screen index (0-based). -1 = use configured default.
        confidence: Detection confidence [0, 1]
    """
    return {
        "type": "pointer",
        "x": x,
        "y": y,
        "fingerCount": 1,
        "screenIndex": screen_index,
        "confidence": confidence
    }

def zoom_gesture(x: float, y: float, stretch: float, screen_index: int = -1, confidence: float = 0.95) -> dict:
    """
    Two-finger zoom gesture - triggers Ctrl+MouseWheel zoom.
    
    Args:
        x: Center X position of the two fingers [0, 1]
        y: Center Y position of the two fingers [0, 1]
        stretch: Cumulative stretch value (ratio of current to initial distance)
                 > 1.0 = zoom in (fingers spreading)
                 < 1.0 = zoom out (fingers pinching)
        screen_index: Target screen index (0-based). -1 = use configured default.
        confidence: Detection confidence [0, 1]
    """
    return {
        "type": "two_finger",
        "x": x,
        "y": y,
        "fingerCount": 2,
        "screenIndex": screen_index,
        "stretch": stretch,
        "confidence": confidence
    }

def swipe_gesture(direction: str, confidence: float = 0.95) -> dict:
    """
    Swipe gesture - triggers Alt+Tab or Win+Tab.
    
    Args:
        direction: One of "left", "right", "up", "down"
        confidence: Detection confidence [0, 1]
    """
    return {
        "type": "swipe",
        "swipeDirection": direction,
        "confidence": confidence
    }

def pinch_gesture(x: float, y: float, active: bool, screen_index: int = -1, confidence: float = 0.95) -> dict:
    """
    Pinch/grab gesture - starts/ends a click-and-hold.
    
    Args:
        x: Position X [0, 1]
        y: Position Y [0, 1]
        active: True = mouse down, False = mouse up
        screen_index: Target screen index (0-based). -1 = use configured default.
        confidence: Detection confidence [0, 1]
    """
    return {
        "type": "pinch",
        "x": x,
        "y": y,
        "screenIndex": screen_index,
        "pinchActive": active,
        "confidence": confidence
    }

def thumbs_up_gesture(roll: float, confidence: float = 0.95) -> dict:
    """
    Thumbs up gesture with roll - triggers vertical scrolling.
    
    Args:
        roll: Roll angle/value. Positive = scroll up, Negative = scroll down
              The controller accumulates changes and converts to wheel events.
        confidence: Detection confidence [0, 1]
    """
    return {
        "type": "thumbs_up",
        "roll": roll,
        "confidence": confidence
    }

def clap_gesture(confidence: float = 0.95) -> dict:
    """
    Clap gesture - toggles between Cursor and Laser Pointer modes.
    
    Args:
        confidence: Detection confidence [0, 1]
    """
    return {
        "type": "clap",
        "confidence": confidence
    }

def no_gesture() -> dict:
    """No gesture detected - releases any active pinch."""
    return {
        "type": "none"
    }

# ============================================================
# DEMO SCENARIOS
# ============================================================

def demo_cursor_movement(sock):
    """Demonstrate cursor movement in a figure-8 pattern."""
    print("Demo: Moving cursor in figure-8 pattern...")
    
    for t in range(200):
        # Parametric figure-8
        angle = t * 0.05
        x = 0.5 + 0.3 * math.sin(angle)
        y = 0.5 + 0.15 * math.sin(2 * angle)
        
        send_gesture(sock, pointer_gesture(x, y))
        time.sleep(0.016)  # ~60 FPS
    
    print("Done!")

def demo_zoom(sock):
    """Demonstrate zoom in and out."""
    print("Demo: Zooming in...")
    
    # Zoom in (stretch increases from 1.0)
    for i in range(30):
        stretch = 1.0 + (i * 0.05)
        send_gesture(sock, zoom_gesture(0.5, 0.5, stretch))
        time.sleep(0.05)
    
    print("Demo: Zooming out...")
    
    # Zoom out (stretch decreases)
    for i in range(60):
        stretch = 2.5 - (i * 0.05)
        send_gesture(sock, zoom_gesture(0.5, 0.5, stretch))
        time.sleep(0.05)
    
    print("Done!")

def demo_swipe(sock):
    """Demonstrate swipe gestures."""
    print("Demo: Swipe right (Alt+Tab)...")
    send_gesture(sock, swipe_gesture("right"))
    time.sleep(1.0)
    
    print("Demo: Swipe left (Shift+Alt+Tab)...")
    send_gesture(sock, swipe_gesture("left"))
    time.sleep(1.0)
    
    print("Demo: Swipe up (Win+Tab)...")
    send_gesture(sock, swipe_gesture("up"))
    time.sleep(1.0)
    
    print("Done!")

def demo_drag(sock):
    """Demonstrate click and drag with pinch."""
    print("Demo: Starting drag...")
    
    # Start pinch at position
    send_gesture(sock, pinch_gesture(0.3, 0.3, active=True))
    time.sleep(0.1)
    
    # Drag across screen
    for i in range(50):
        x = 0.3 + (i * 0.01)
        y = 0.3 + (i * 0.01)
        send_gesture(sock, pinch_gesture(x, y, active=True))
        time.sleep(0.02)
    
    # Release
    send_gesture(sock, pinch_gesture(0.8, 0.8, active=False))
    time.sleep(0.1)
    send_gesture(sock, no_gesture())
    
    print("Done!")

def demo_scroll(sock):
    """Demonstrate vertical scrolling with thumbs up."""
    print("Demo: Scrolling down...")
    
    roll = 0.0
    for i in range(30):
        roll -= 0.5
        send_gesture(sock, thumbs_up_gesture(roll))
        time.sleep(0.05)
    
    print("Demo: Scrolling up...")
    
    for i in range(30):
        roll += 0.5
        send_gesture(sock, thumbs_up_gesture(roll))
        time.sleep(0.05)
    
    print("Done!")

def demo_laser_mode(sock):
    """Demonstrate laser pointer mode toggle."""
    print("Demo: Toggling to Laser Pointer mode...")
    send_gesture(sock, clap_gesture())
    time.sleep(1.0)
    
    print("Demo: Moving laser pointer...")
    for t in range(1000):
        angle = t * 0.1
        x = 0.5 + 0.3 * math.cos(angle)
        y = 0.5 + 0.2 * math.sin(angle)
        send_gesture(sock, pointer_gesture(x, y))
        time.sleep(0.0016)
    
    print("Demo: Toggling back to Cursor mode...")
    send_gesture(sock, clap_gesture())
    time.sleep(0.5)
    
    print("Done!")

# ============================================================
# MAIN
# ============================================================

def main():
    print(f"Gesture Sender Example - Sending to {UDP_IP}:{UDP_PORT}")
    print("-" * 50)
    print("Make sure the C# GestureUdpReceiver is listening!")
    print("-" * 50)
    
    sock = create_udp_socket()
    
    while True:
        print("\nSelect a demo:")
        print("1. Cursor movement (figure-8)")
        print("2. Zoom in/out")
        print("3. Swipe gestures (Alt+Tab/Win+Tab)")
        print("4. Drag operation (pinch)")
        print("5. Vertical scrolling (thumbs up)")
        print("6. Laser pointer mode toggle (clap)")
        print("0. Exit")
        
        choice = input("\nEnter choice: ").strip()
        
        if choice == "1":
            demo_cursor_movement(sock)
        elif choice == "2":
            demo_zoom(sock)
        elif choice == "3":
            demo_swipe(sock)
        elif choice == "4":
            demo_drag(sock)
        elif choice == "5":
            demo_scroll(sock)
        elif choice == "6":
            demo_laser_mode(sock)
        elif choice == "0":
            break
        else:
            print("Invalid choice")
    
    sock.close()
    print("Goodbye!")

if __name__ == "__main__":
    main()
