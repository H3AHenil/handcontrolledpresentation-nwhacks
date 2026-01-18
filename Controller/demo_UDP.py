"""
Interactive Demo for UDP Gesture Controller

This script demonstrates all the gesture APIs with visual feedback and delays,
similar to gesture_sender_example.py. It actually sends UDP packets to the
C# GestureController.

Usage:
    python demo_UDP.py

Make sure the C# GestureUdpReceiver is listening before running!
"""

import time
import math
from UDP import UDPGestureController


# ============================================================
# DEMO SCENARIOS
# ============================================================

def demo_pointer_movement(ctrl: UDPGestureController):
    """Demonstrate cursor movement in a figure-8 pattern."""
    print("Demo: Moving cursor in figure-8 pattern...")

    for t in range(200):
        # Parametric figure-8
        angle = t * 0.05
        x = 0.5 + 0.3 * math.sin(angle)
        y = 0.5 + 0.15 * math.sin(2 * angle)

        ctrl.pointer(x, y)
        time.sleep(0.016)  # ~60 FPS

    print("Done!")


def demo_two_finger_zoom(ctrl: UDPGestureController):
    """Demonstrate zoom in and out."""
    print("Demo: Zooming in...")

    # Zoom in (stretch increases from 1.0)
    for i in range(30):
        stretch = 1.0 + (i * 0.05)
        ctrl.two_finger_zoom(0.5, 0.5, stretch)
        time.sleep(0.05)

    print("Demo: Zooming out...")

    # Zoom out (stretch decreases)
    for i in range(60):
        stretch = 2.5 - (i * 0.05)
        ctrl.two_finger_zoom(0.5, 0.5, stretch)
        time.sleep(0.05)

    print("Done!")


def demo_swipe_gestures(ctrl: UDPGestureController):
    """Demonstrate swipe gestures."""
    print("Demo: Swipe right (Alt+Tab)...")
    ctrl.swipe("right")
    time.sleep(1.0)

    print("Demo: Swipe left (Shift+Alt+Tab)...")
    ctrl.swipe("left")
    time.sleep(1.0)

    print("Demo: Swipe up (Win+Tab)...")
    ctrl.swipe("up")
    time.sleep(1.0)

    print("Demo: Swipe down...")
    ctrl.swipe("down")
    time.sleep(1.0)

    print("Done!")


def demo_pinch_drag(ctrl: UDPGestureController):
    """Demonstrate click and drag with pinch."""
    print("Demo: Starting drag operation...")

    # Start pinch at position (mouse down)
    ctrl.pinch(0.3, 0.3, active=True)
    time.sleep(0.1)

    # Drag across screen
    for i in range(50):
        x = 0.3 + (i * 0.01)
        y = 0.3 + (i * 0.01)
        ctrl.pinch(x, y, active=True)
        time.sleep(0.02)

    # Release (mouse up)
    ctrl.pinch(0.8, 0.8, active=False)
    time.sleep(0.1)
    ctrl.no_gesture()

    print("Done!")


def demo_thumbs_up_scroll(ctrl: UDPGestureController):
    """Demonstrate vertical scrolling with thumbs up gesture."""
    print("Demo: Scrolling down with thumbs up...")

    roll = 0.0
    for i in range(30):
        roll -= 0.5
        ctrl.thumbs_up(roll)
        time.sleep(0.05)

    print("Demo: Scrolling up with thumbs up...")

    for i in range(30):
        roll += 0.5
        ctrl.thumbs_up(roll)
        time.sleep(0.05)

    print("Done!")


def demo_clap_mode_toggle(ctrl: UDPGestureController):
    """Demonstrate laser pointer mode toggle with clap."""
    print("Demo: Toggling to Laser Pointer mode with clap...")
    ctrl.clap()
    time.sleep(1.0)

    print("Demo: Moving laser pointer in circle...")
    for t in range(100):
        angle = t * 0.1
        x = 0.5 + 0.3 * math.cos(angle)
        y = 0.5 + 0.2 * math.sin(angle)
        ctrl.pointer(x, y)
        time.sleep(0.016)

    print("Demo: Toggling back to Cursor mode with clap...")
    ctrl.clap()
    time.sleep(0.5)

    print("Done!")


def demo_legacy_click(ctrl: UDPGestureController):
    """Demonstrate legacy click commands."""
    print("Demo: Left click...")
    ctrl.left_click()
    time.sleep(0.5)

    print("Demo: Right click...")
    ctrl.right_click()
    time.sleep(0.5)

    print("Done!")


def demo_legacy_move(ctrl: UDPGestureController):
    """Demonstrate legacy move commands."""
    print("Demo: Moving cursor relative (right and down)...")
    for i in range(20):
        ctrl.move_relative(10, 5)
        time.sleep(0.05)

    print("Demo: Moving cursor relative (left and up)...")
    for i in range(20):
        ctrl.move_relative(-10, -5)
        time.sleep(0.05)

    print("Demo: Moving to absolute position (center of screen 0)...")
    ctrl.move_absolute(0, 960, 540)
    time.sleep(0.5)

    print("Done!")


def demo_legacy_scroll(ctrl: UDPGestureController):
    """Demonstrate legacy scroll commands."""
    print("Demo: Scrolling up...")
    for i in range(5):
        ctrl.scroll(120)
        time.sleep(0.2)

    print("Demo: Scrolling down...")
    for i in range(5):
        ctrl.scroll(-120)
        time.sleep(0.2)

    print("Done!")


def demo_legacy_zoom(ctrl: UDPGestureController):
    """Demonstrate legacy zoom commands."""
    print("Demo: Zooming in with Ctrl+Wheel...")
    for i in range(5):
        ctrl.zoom_in(1)
        time.sleep(0.3)

    print("Demo: Zooming out with Ctrl+Wheel...")
    for i in range(5):
        ctrl.zoom_out(1)
        time.sleep(0.3)

    print("Done!")


def demo_legacy_pinch(ctrl: UDPGestureController):
    """Demonstrate legacy pinch commands."""
    print("Demo: Pinch out (zoom in)...")
    for i in range(3):
        ctrl.pinch_out(2)
        time.sleep(0.3)

    print("Demo: Pinch in (zoom out)...")
    for i in range(3):
        ctrl.pinch_in(2)
        time.sleep(0.3)

    print("Done!")


def run_all_demos(ctrl: UDPGestureController):
    """Run all demos in sequence."""
    demos = [
        ("Pointer Movement", demo_pointer_movement),
        ("Two-Finger Zoom", demo_two_finger_zoom),
        ("Swipe Gestures", demo_swipe_gestures),
        ("Pinch Drag", demo_pinch_drag),
        ("Thumbs Up Scroll", demo_thumbs_up_scroll),
        ("Clap Mode Toggle", demo_clap_mode_toggle),
        ("Legacy Click", demo_legacy_click),
        ("Legacy Move", demo_legacy_move),
        ("Legacy Scroll", demo_legacy_scroll),
        ("Legacy Zoom", demo_legacy_zoom),
        ("Legacy Pinch", demo_legacy_pinch),
    ]

    for name, demo_func in demos:
        print(f"\n{'='*50}")
        print(f"Running: {name}")
        print('='*50)
        demo_func(ctrl)
        time.sleep(0.5)

    print("\n" + "="*50)
    print("All demos completed!")
    print("="*50)


# ============================================================
# MAIN
# ============================================================

def main():
    print("="*60)
    print("UDP Gesture Controller - Interactive Demo")
    print("="*60)
    print(f"Gesture Port: {UDPGestureController.GESTURE_PORT}")
    print(f"Legacy Port: {UDPGestureController.LEGACY_PORT}")
    print("-"*60)
    print("Make sure the C# GestureUdpReceiver is listening!")
    print("-"*60)

    with UDPGestureController() as ctrl:
        while True:
            print("\nSelect a demo:")
            print("--- Gesture API (JSON Protocol) ---")
            print("1. Pointer movement (figure-8)")
            print("2. Two-finger zoom in/out")
            print("3. Swipe gestures (Alt+Tab/Win+Tab)")
            print("4. Pinch drag operation")
            print("5. Thumbs up scrolling")
            print("6. Clap mode toggle (laser pointer)")
            print("--- Legacy API (Text Protocol) ---")
            print("7. Left/Right click")
            print("8. Relative/Absolute move")
            print("9. Scroll up/down")
            print("10. Zoom in/out (Ctrl+Wheel)")
            print("11. Pinch in/out")
            print("--- Other ---")
            print("A. Run all demos")
            print("0. Exit")

            choice = input("\nEnter choice: ").strip().lower()

            if choice == "1":
                demo_pointer_movement(ctrl)
            elif choice == "2":
                demo_two_finger_zoom(ctrl)
            elif choice == "3":
                demo_swipe_gestures(ctrl)
            elif choice == "4":
                demo_pinch_drag(ctrl)
            elif choice == "5":
                demo_thumbs_up_scroll(ctrl)
            elif choice == "6":
                demo_clap_mode_toggle(ctrl)
            elif choice == "7":
                demo_legacy_click(ctrl)
            elif choice == "8":
                demo_legacy_move(ctrl)
            elif choice == "9":
                demo_legacy_scroll(ctrl)
            elif choice == "10":
                demo_legacy_zoom(ctrl)
            elif choice == "11":
                demo_legacy_pinch(ctrl)
            elif choice == "a":
                run_all_demos(ctrl)
            elif choice == "0":
                break
            else:
                print("Invalid choice, please try again.")

    print("\nGoodbye!")


if __name__ == "__main__":
    main()

