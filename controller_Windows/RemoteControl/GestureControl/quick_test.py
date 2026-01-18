"""
Quick test script to verify the gesture control system is working.
This script sends a sequence of gestures automatically.

Usage:
    1. Start the RemoteControl C# application
    2. Click "Start Gesture Listener (Port 9090)" button
    3. Run this script: python quick_test.py
"""

import socket
import json
import time
import math

UDP_IP = "127.0.0.1"
UDP_PORT = 9090

# Target screen index (0 = first/primary screen, 1 = second screen, etc.)
# Set to -1 to use the default configured in the C# app
TARGET_SCREEN = 0

# Device ID for multi-device setups (empty string matches all)
DEVICE_ID = "device_1"

def send_gesture(sock, gesture_data: dict):
    """Send gesture data as JSON over UDP."""
    json_data = json.dumps(gesture_data)
    sock.sendto(json_data.encode('utf-8'), (UDP_IP, UDP_PORT))
    print(f"Sent: {gesture_data.get('type', 'unknown')}")

def main():
    print("=" * 50)
    print("Gesture Control Quick Test")
    print(f"Sending to {UDP_IP}:{UDP_PORT}")
    print(f"Target Screen: {TARGET_SCREEN}")
    print(f"Device ID: {DEVICE_ID}")
    print("=" * 50)
    print("\nMake sure the C# app is running and the listener is started!")
    print("Press Enter to begin test sequence...")
    input()
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        # Test 1: Move cursor in a circle
        print("\n[Test 1] Moving cursor in a circle...")
        for t in range(50):
            angle = t * 0.15
            x = 0.5 + 0.2 * math.cos(angle)
            y = 0.5 + 0.2 * math.sin(angle)
            send_gesture(sock, {
                "type": "pointer",
                "deviceId": DEVICE_ID,
                "x": x,
                "y": y,
                "screenIndex": TARGET_SCREEN,
                "confidence": 0.95
            })
            time.sleep(0.03)
        
        print("Circle complete!")
        time.sleep(0.5)
        
        # Test 2: Zoom in
        print("\n[Test 2] Zoom in...")
        for i in range(10):
            send_gesture(sock, {
                "type": "two_finger",
                "deviceId": DEVICE_ID,
                "x": 0.5,
                "y": 0.5,
                "screenIndex": TARGET_SCREEN,
                "stretch": 1.0 + (i * 0.1),
                "confidence": 0.95
            })
            time.sleep(0.1)
        
        print("Zoom in complete!")
        time.sleep(0.5)
        
        # Test 3: Zoom out
        print("\n[Test 3] Zoom out...")
        for i in range(10):
            send_gesture(sock, {
                "type": "two_finger",
                "deviceId": DEVICE_ID,
                "x": 0.5,
                "y": 0.5,
                "screenIndex": TARGET_SCREEN,
                "stretch": 2.0 - (i * 0.1),
                "confidence": 0.95
            })
            time.sleep(0.1)
        
        print("Zoom out complete!")
        time.sleep(0.5)
        
        # Test 4: Toggle laser mode (clap)
        print("\n[Test 4] Toggle laser mode (clap)...")
        send_gesture(sock, {
            "type": "clap",
            "deviceId": DEVICE_ID,
            "confidence": 0.95
        })
        time.sleep(1.0)
        
        # Move laser pointer
        print("Moving laser pointer...")
        for t in range(30):
            angle = t * 0.2
            x = 0.5 + 0.15 * math.cos(angle)
            y = 0.5 + 0.15 * math.sin(angle)
            send_gesture(sock, {
                "type": "pointer",
                "deviceId": DEVICE_ID,
                "x": x,
                "y": y,
                "screenIndex": TARGET_SCREEN,
                "confidence": 0.95
            })
            time.sleep(0.03)
        
        # Toggle back to cursor mode
        print("Toggle back to cursor mode...")
        send_gesture(sock, {
            "type": "clap",
            "deviceId": DEVICE_ID,
            "confidence": 0.95
        })
        time.sleep(0.5)
        
        # Test 5: Scroll
        print("\n[Test 5] Scroll down then up...")
        roll = 0.0
        for i in range(10):
            roll -= 1.0
            send_gesture(sock, {
                "type": "thumbs_up",
                "deviceId": DEVICE_ID,
                "roll": roll,
                "confidence": 0.95
            })
            time.sleep(0.1)
        
        for i in range(10):
            roll += 1.0
            send_gesture(sock, {
                "type": "thumbs_up",
                "deviceId": DEVICE_ID,
                "roll": roll,
                "confidence": 0.95
            })
            time.sleep(0.1)
        
        print("Scroll complete!")
        
        print("\n" + "=" * 50)
        print("All tests completed!")
        print("=" * 50)
        
    finally:
        sock.close()

if __name__ == "__main__":
    main()
