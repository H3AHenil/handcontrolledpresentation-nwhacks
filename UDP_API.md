# UDP Remote Control API

This repository provides two UDP-based protocols for remote control:

1. **Legacy Text Protocol** (Port 8080): Simple text-based commands for basic mouse control
2. **Gesture JSON Protocol** (Port 9090): Rich JSON-based protocol for gesture-driven control

---

## Table of Contents

- [1. Networking](#1-networking)
- [2. Gesture JSON Protocol (Port 9090)](#2-gesture-json-protocol-port-9090)
- [3. Legacy Text Protocol (Port 8080)](#3-legacy-text-protocol-port-8080)
- [4. Python API Reference](#4-python-api-reference)
- [5. Notes / Caveats](#5-notes--caveats)

---

## 1. Networking

| Property | Gesture Protocol | Legacy Protocol |
|----------|------------------|-----------------|
| Transport | UDP | UDP |
| Default Port | 9090 | 8080 |
| Default IP | 127.0.0.1 | 255.255.255.255 (broadcast) |
| Encoding | UTF-8 | UTF-8 |
| Format | JSON | Plain text |

---

## 2. Gesture JSON Protocol (Port 9090)

The gesture protocol uses JSON messages to transmit gesture data from a Computer Vision module to the C# GestureController.

### 2.1 Common Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Gesture type identifier (required) |
| `confidence` | float | Detection confidence [0, 1] (optional, default: 0.95) |
| `screenIndex` | int | Target screen index, -1 = default (optional) |

### 2.2 Gesture Types

#### 2.2.1 Pointer Gesture

Moves the cursor to a normalized screen position.

```json
{
    "type": "pointer",
    "x": 0.5,
    "y": 0.5,
    "fingerCount": 1,
    "screenIndex": -1,
    "confidence": 0.95
}
```

| Field | Type | Description |
|-------|------|-------------|
| `x` | float | Normalized X position [0, 1], 0=left, 1=right |
| `y` | float | Normalized Y position [0, 1], 0=top, 1=bottom |
| `fingerCount` | int | Number of fingers (1 for pointer) |

#### 2.2.2 Two-Finger Zoom Gesture

Triggers Ctrl+MouseWheel zoom centered at the specified position.

```json
{
    "type": "two_finger",
    "x": 0.5,
    "y": 0.5,
    "fingerCount": 2,
    "screenIndex": -1,
    "stretch": 1.5,
    "confidence": 0.95
}
```

| Field | Type | Description |
|-------|------|-------------|
| `x` | float | Center X of the two fingers [0, 1] |
| `y` | float | Center Y of the two fingers [0, 1] |
| `stretch` | float | Ratio of current to initial finger distance. >1.0 = zoom in, <1.0 = zoom out |

#### 2.2.3 Swipe Gesture

Triggers window switching actions.

```json
{
    "type": "swipe",
    "swipeDirection": "right",
    "confidence": 0.95
}
```

| Field | Type | Description |
|-------|------|-------------|
| `swipeDirection` | string | One of: `"left"`, `"right"`, `"up"`, `"down"` |

| Direction | Action |
|-----------|--------|
| `right` | Alt+Tab (next window) |
| `left` | Shift+Alt+Tab (previous window) |
| `up` | Win+Tab (task view) |
| `down` | Reserved |

#### 2.2.4 Pinch Gesture

Click-and-hold for drag operations.

```json
{
    "type": "pinch",
    "x": 0.5,
    "y": 0.5,
    "screenIndex": -1,
    "pinchActive": true,
    "confidence": 0.95
}
```

| Field | Type | Description |
|-------|------|-------------|
| `x` | float | Cursor X position [0, 1] |
| `y` | float | Cursor Y position [0, 1] |
| `pinchActive` | bool | `true` = mouse down, `false` = mouse up |

#### 2.2.5 Thumbs Up Gesture

Vertical scrolling via roll angle.

```json
{
    "type": "thumbs_up",
    "roll": -5.0,
    "confidence": 0.95
}
```

| Field | Type | Description |
|-------|------|-------------|
| `roll` | float | Roll angle/value. Positive = scroll up, Negative = scroll down |

#### 2.2.6 Clap Gesture

Toggle between Cursor mode and Laser Pointer mode.

```json
{
    "type": "clap",
    "confidence": 0.95
}
```

#### 2.2.7 No Gesture

Release any active gesture state.

```json
{
    "type": "none"
}
```

---

## 3. Legacy Text Protocol (Port 8080)

Plain text commands for basic mouse control. One command per UDP datagram.

### 3.1 Click Commands

| Command | Description |
|---------|-------------|
| `LeftClick` | Left mouse button click |
| `RightClick` | Right mouse button click |

### 3.2 Move Commands

| Command | Description |
|---------|-------------|
| `Move:<dx>,<dy>` | Relative cursor movement (pixels) |
| `Abs:<screen>,<x>,<y>` | Absolute move to screen coordinates |

Examples:
- `Move:10,-5` - Move 10px right, 5px up
- `Abs:0,960,540` - Move to (960, 540) on screen 0

### 3.3 Scroll Command

| Command | Description |
|---------|-------------|
| `Scroll:<delta>` | Mouse wheel scroll. Positive=up, Negative=down |

Examples:
- `Scroll:120` - Scroll up one notch
- `Scroll:-120` - Scroll down one notch

### 3.4 Zoom Command

| Command | Description |
|---------|-------------|
| `Zoom:<steps>` | Ctrl+Wheel zoom. Positive=in, Negative=out |

Examples:
- `Zoom:1` - Zoom in one step
- `Zoom:-2` - Zoom out two steps

### 3.5 Pinch Command

| Command | Description |
|---------|-------------|
| `Pinch:<direction>,<steps>` | Touch pinch gesture |

Semantics:
- `direction`: `1` = zoom in (pinch out), `-1` = zoom out (pinch in)
- `steps`: Intensity/steps

Examples:
- `Pinch:1,2` - Zoom in with intensity 2
- `Pinch:-1,3` - Zoom out with intensity 3

---

## 4. Python API Reference

The `UDPGestureController` class provides a Python interface for both protocols.

### 4.1 Initialization

```python
from UDP import UDPGestureController

# Default: localhost, gesture port 9090, legacy port 8080
controller = UDPGestureController()

# With custom settings
controller = UDPGestureController(
    gesture_port=9090,
    legacy_port=8080,
    target_ip="127.0.0.1",
    broadcast=False
)

# Context manager usage
with UDPGestureController() as ctrl:
    ctrl.pointer(0.5, 0.5)
```

### 4.2 Gesture API Methods

| Method | Description |
|--------|-------------|
| `pointer(x, y, screen_index=-1, confidence=0.95)` | Move cursor to normalized position |
| `two_finger_zoom(x, y, stretch, screen_index=-1, confidence=0.95)` | Two-finger zoom gesture |
| `swipe(direction, confidence=0.95)` | Swipe gesture (left/right/up/down) |
| `pinch(x, y, active, screen_index=-1, confidence=0.95)` | Pinch/grab for drag operations |
| `thumbs_up(roll, confidence=0.95)` | Thumbs up for vertical scrolling |
| `clap(confidence=0.95)` | Toggle cursor/laser pointer mode |
| `no_gesture()` | Release active gesture state |

### 4.3 Legacy API Methods

| Method | Description |
|--------|-------------|
| `left_click()` | Left mouse click |
| `right_click()` | Right mouse click |
| `move_relative(dx, dy)` | Move cursor by offset (pixels) |
| `move_absolute(screen, x, y)` | Move to absolute screen position |
| `scroll(delta)` | Mouse wheel scroll |
| `zoom(steps)` | Ctrl+Wheel zoom |
| `zoom_in(steps=1)` | Zoom in |
| `zoom_out(steps=1)` | Zoom out |
| `legacy_pinch(direction, steps)` | Touch pinch ("in"/"out") |
| `pinch_in(steps=1)` | Pinch in (zoom out) |
| `pinch_out(steps=1)` | Pinch out (zoom in) |
| `send_raw(command)` | Send raw protocol command |

### 4.4 Usage Examples

```python
from UDP import UDPGestureController
import time

with UDPGestureController() as ctrl:
    # Move cursor in a circle
    import math
    for t in range(100):
        x = 0.5 + 0.3 * math.cos(t * 0.1)
        y = 0.5 + 0.3 * math.sin(t * 0.1)
        ctrl.pointer(x, y)
        time.sleep(0.016)
    
    # Zoom in
    for i in range(10):
        ctrl.two_finger_zoom(0.5, 0.5, 1.0 + i * 0.1)
        time.sleep(0.05)
    
    # Swipe to switch windows
    ctrl.swipe("right")
    time.sleep(0.5)
    
    # Drag operation
    ctrl.pinch(0.3, 0.3, active=True)
    for i in range(20):
        ctrl.pinch(0.3 + i * 0.02, 0.3 + i * 0.02, active=True)
        time.sleep(0.02)
    ctrl.pinch(0.7, 0.7, active=False)
    ctrl.no_gesture()
    
    # Scroll with thumbs up
    roll = 0.0
    for i in range(20):
        roll -= 0.5
        ctrl.thumbs_up(roll)
        time.sleep(0.05)
    
    # Toggle laser pointer mode
    ctrl.clap()
```

---

## 5. Notes / Caveats

1. **Screen index order** comes from Windows monitor enumeration and may not match Display Settings order.
2. **Firewall**: Allow inbound UDP on ports 8080 and 9090 for the controlled app.
3. **Touch support**: Not all applications support touch pinch; a fallback to Ctrl+Wheel is implemented.
4. **Gesture debouncing**: Swipe and clap gestures have built-in debounce intervals (500ms and 800ms respectively).
5. **Confidence threshold**: Gestures with confidence below 0.7 are ignored by default.
6. **Backward compatibility**: `UDPRemoteController` is an alias for `UDPGestureController`.
