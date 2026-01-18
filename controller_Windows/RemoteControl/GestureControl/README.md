# Hand Gesture Control Module

A robust C# architecture for mapping hand gestures to Windows OS actions using Win32 APIs (P/Invoke).

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Computer Vision Module                          │
│                 (Python/C++ - Your gesture detection)               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ JSON over UDP
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     GestureUdpReceiver                              │
│         Receives JSON gesture data and parses it                    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ GestureData struct
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     GestureDataAdapter                              │
│      Debouncing, state management, gesture transitions              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ IGestureInputHandler interface
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     GestureController                               │
│           Main controller with mode management                      │
│     ┌───────────────────┬───────────────────────────┐              │
│     │   Cursor Mode     │    Laser Pointer Mode     │              │
│     └─────────┬─────────┴─────────────┬─────────────┘              │
│               │                       │                             │
│               ▼                       ▼                             │
│    ┌─────────────────────┐  ┌─────────────────────┐                │
│    │ Win32InputSimulator │  │ LaserPointerOverlay │                │
│    │   (P/Invoke APIs)   │  │  (WPF Click-Through) │                │
│    └─────────────────────┘  └─────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. `IGestureInputHandler` Interface
The main interface for gesture input. Implement this to create custom controllers.

```csharp
public interface IGestureInputHandler
{
    GestureMode CurrentMode { get; }
    bool IsPinchActive { get; }
    int TargetScreenIndex { get; set; }  // Multi-screen support
    
    event EventHandler<GestureModeChangedEventArgs>? ModeChanged;
    event EventHandler<ScreenChangedEventArgs>? TargetScreenChanged;
    
    void UpdateFingerPosition(float normalizedX, float normalizedY, int fingerCount = 1, int screenIndex = -1);
    void UpdateZoom(float cumulativeStretchValue);
    void TriggerSwipe(SwipeDirection direction);
    void StartPinch();
    void EndPinch();
    void UpdateThumbsUpRoll(float rollValue);
    void ToggleLaserMode();
    void SetMode(GestureMode mode);
    void Shutdown();
}
```

### 2. `GestureController`
Main implementation that maps gestures to Windows actions.

### 3. `Win32InputSimulator`
Low-level P/Invoke wrapper for Windows input simulation:
- Cursor positioning (`SetCursorPos`)
- Mouse events (`mouse_event`)
- Keyboard events (`keybd_event`)
- Scroll wheel (vertical/horizontal)
- Zoom via Ctrl+Wheel

### 4. `LaserPointerOverlay`
WPF transparent overlay window for laser pointer mode:
- Click-through (`WS_EX_TRANSPARENT`, `WS_EX_LAYERED`)
- Red dot with radial gradient glow effect
- Trail effect with fade animation
- **Multi-monitor support** - can target a specific screen or all screens

### 5. `ScreenManager`
Manages multi-monitor configuration:
- Enumerates all connected screens
- Provides screen bounds and information
- Converts normalized coordinates to screen coordinates

### 6. `GestureDataAdapter`
Converts raw CV data to gesture actions with:
- Debouncing for discrete gestures
- State tracking for pinch (press/release)
- Automatic gesture transition handling

### 7. `GestureUdpReceiver`
UDP listener for receiving JSON gesture data from CV module.

## Gesture Mappings

| Gesture | Input | Action |
|---------|-------|--------|
| **Pointer (1 Finger)** | Continuous (x, y) | Absolute cursor movement via `SetCursorPos` |
| **Pointer (2 Fingers)** | Cumulative stretch (Σ) | Delta → Ctrl + MouseWheel for zoom |
| **Swipe** | Direction (discrete) | Alt+Tab (left/right) or Win+Tab (up) |
| **Pinch** | Active state | Left Mouse Down → Up on release |
| **Thumbs Up** | Roll value | Vertical scroll via `mouse_event` wheel |
| **Clap** | Discrete | Toggle Cursor ↔ Laser Pointer mode |

## Quick Start

### Option 1: Direct API Usage

```csharp
using TestOnRemoteControl.GestureControl;

// Create controller
var controller = new GestureController();

// Subscribe to mode changes
controller.ModeChanged += (s, e) => Console.WriteLine($"Mode: {e.NewMode}");

// Update pointer position (normalized 0-1)
controller.UpdateFingerPosition(0.5f, 0.5f);

// Toggle laser mode (simulates clap)
controller.ToggleLaserMode();

// Start drag operation (simulates pinch)
controller.StartPinch();
controller.UpdateFingerPosition(0.6f, 0.6f); // Drag
controller.EndPinch();

// Zoom
controller.UpdateZoom(1.5f); // Zoom in
controller.UpdateZoom(1.0f); // Zoom back

// Swipe for app switching
controller.TriggerSwipe(SwipeDirection.Right); // Alt+Tab

// Scroll with thumbs up roll
controller.UpdateThumbsUpRoll(2.0f); // Scroll up

// Cleanup
controller.Dispose();
```

### Option 2: Using the Adapter with Raw Data

```csharp
using TestOnRemoteControl.GestureControl;

var controller = new GestureController();
var adapter = new GestureDataAdapter(controller);

// Process gesture data from your CV module
var gestureData = new GestureData
{
    Type = GestureType.Pointer,
    NormalizedX = 0.5f,
    NormalizedY = 0.5f,
    Confidence = 0.95f,
    Timestamp = DateTime.UtcNow
};

adapter.ProcessGestureData(gestureData);
```

### Option 3: UDP Integration

Start the UDP receiver to accept JSON packets from your CV module:

```csharp
using TestOnRemoteControl.GestureControl;

var controller = new GestureController();
var receiver = new GestureUdpReceiver(9090, controller);

receiver.GestureReceived += (s, data) => 
    Console.WriteLine($"Gesture: {data.Type}");

receiver.Start();

// Later...
await receiver.StopAsync();
receiver.Dispose();
controller.Dispose();
```

## JSON Protocol for UDP

Send JSON packets to the UDP receiver:

```json
{
    "type": "pointer",
    "x": 0.5,
    "y": 0.5,
    "fingerCount": 1,
    "screenIndex": 0,
    "stretch": 1.0,
    "roll": 0.0,
    "swipeDirection": "right",
    "pinchActive": false,
    "confidence": 0.95
}
```

### Field Reference:

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Gesture type (see below) |
| `x` | float | Normalized X position [0, 1] |
| `y` | float | Normalized Y position [0, 1] |
| `fingerCount` | int | Number of fingers (1 or 2) |
| `screenIndex` | int | Target screen (0-based, -1 = use default) |
| `stretch` | float | Zoom stretch value (1.0 = neutral) |
| `roll` | float | Roll angle for scrolling |
| `swipeDirection` | string | Swipe direction |
| `pinchActive` | bool | Whether pinch is active |
| `confidence` | float | Detection confidence [0, 1] |

### Supported `type` values:
- `"pointer"` or `"point"` - Single finger pointer
- `"two_finger"` or `"zoom"` - Two-finger zoom gesture
- `"swipe"` - Swipe gesture
- `"pinch"` or `"grab"` - Pinch/grab gesture
- `"thumbs_up"` or `"thumb"` - Thumbs up for scrolling
- `"clap"` - Clap for mode toggle
- `"none"` - No gesture detected

### Swipe directions:
- `"left"`, `"right"`, `"up"`, `"down"`

## Configuration

Customize the controller behavior:

```csharp
var config = new GestureController.ControllerConfiguration
{
    ZoomSensitivity = 150.0f,      // How fast zoom responds
    ScrollSensitivity = 80.0f,     // How fast scroll responds  
    ZoomThreshold = 0.01f,         // Minimum change to trigger zoom
    ScrollThreshold = 0.05f,       // Minimum change to trigger scroll
    MovementSmoothing = 0.2f,      // Position smoothing (0-1)
    UseWinTabForSwipe = false      // Use Win+Tab instead of Alt+Tab
};

var controller = new GestureController(config);
```

## Laser Pointer Mode

When laser pointer mode is active:
1. System cursor is hidden
2. Transparent, click-through overlay appears
3. Red dot with glow effect follows gesture position
4. Trail effect fades over time
5. All mouse clicks pass through to underlying windows

Toggle with `controller.ToggleLaserMode()` or send a clap gesture.

## Demo Application

A demo window is included for testing:

```csharp
// In your App.xaml.cs or startup code:
var demoWindow = new TestOnRemoteControl.GestureControl.GestureControlDemoWindow();
demoWindow.Show();
```

Features:
- Test all gesture types with buttons
- UDP listener with configurable port
- Real-time status display
- Activity log

## File Structure

```
GestureControl/
├── IGestureInputHandler.cs           # Core interface
├── GestureController.cs              # Main implementation
├── Win32InputSimulator.cs            # P/Invoke APIs
├── LaserPointerOverlay.cs            # WPF overlay window
├── ScreenManager.cs                  # Multi-monitor support
├── DpiAwareScreenManager.cs          # DPI-aware screen utilities
├── ScreenSelectorWindow.xaml         # Screen selection UI
├── ScreenSelectorWindow.xaml.cs      # Screen selection code-behind
├── ScreenConfigurationWindow.xaml    # Multi-screen AprilTag configuration UI
├── ScreenConfigurationWindow.xaml.cs # Configuration code-behind
├── AprilTagOverlay.cs                # Single-screen AprilTag overlay
├── MultiScreenAprilTagManager.cs     # Multi-screen AprilTag manager (16h5 format)
├── GestureDataAdapter.cs             # CV data adapter
├── GestureUdpReceiver.cs             # UDP listener
├── GestureControlDemoWindow.xaml     # Demo UI
├── GestureControlDemoWindow.xaml.cs  # Demo code-behind
├── quick_test.py                     # Python test script
├── gesture_sender_example.py         # Python example for CV integration
└── README.md                         # This file
```

## Requirements

- .NET 9.0 (Windows)
- WPF support (`<UseWPF>true</UseWPF>`)
- Windows 10/11 (for full feature support)

## Win32 APIs Used

| API | Purpose |
|-----|---------|
| `SetCursorPos` | Absolute cursor positioning |
| `GetCursorPos` | Get current cursor position |
| `mouse_event` | Mouse clicks, movement, wheel |
| `keybd_event` | Keyboard events (modifiers) |
| `GetSystemMetrics` | Screen dimensions |
| `ShowCursor` | Hide/show system cursor |
| `GetWindowLong`/`SetWindowLong` | Click-through overlay |

## Tips for Integration

1. **Position Normalization**: Your CV module should output (x, y) normalized to [0, 1]:
   - `x = landmark_x / frame_width`
   - `y = landmark_y / frame_height`

2. **Cumulative Stretch**: For zoom, track cumulative distance between fingers:
   - `stretch = current_distance / initial_distance`
   - Values > 1.0 = spread (zoom in)
   - Values < 1.0 = pinch (zoom out)

3. **Roll Value**: For thumbs up scrolling:
   - Track the rotation angle of the hand
   - Positive values = scroll up
   - Negative values = scroll down

4. **Confidence Threshold**: The adapter filters gestures with confidence < 0.7 by default. Adjust with:
   ```csharp
   adapter.MinConfidence = 0.8f;
   ```

5. **Frame Rate**: Send updates at 30-60 FPS for smooth control.

## Multi-Screen Support

The gesture control system fully supports multi-monitor setups.

### Using the Screen Selector UI

1. Click **"Select Screen"** button in the main window
2. A dialog shows all connected monitors with their resolution and position
3. Select the target screen and click **OK**
4. The laser pointer and cursor control will now target that screen

### Programmatic Screen Selection

```csharp
// Set target screen by index (0 = primary, 1 = second, etc.)
controller.TargetScreenIndex = 1;

// Listen for screen changes
controller.TargetScreenChanged += (s, e) => 
    Console.WriteLine($"Now targeting: Screen {e.NewScreenIndex + 1}");
```

### Sending Screen Index via UDP

Include `screenIndex` in your JSON packets:

```json
{
    "type": "pointer",
    "x": 0.5,
    "y": 0.5,
    "screenIndex": 0,
    "confidence": 0.95
}
```

- `screenIndex: 0` = First/primary screen
- `screenIndex: 1` = Second screen
- `screenIndex: -1` = Use configured default (set via UI or `TargetScreenIndex`)

### ScreenManager API

Query screen information programmatically:

```csharp
using TestOnRemoteControl.GestureControl;

// Get all screens
var screens = ScreenManager.GetAllScreens();
foreach (var screen in screens)
{
    Console.WriteLine($"Screen {screen.Index}: {screen.Width}x{screen.Height} at ({screen.Left},{screen.Top})");
}

// Get specific screen
var screen = ScreenManager.GetScreen(0);  // Primary screen

// Convert normalized to screen coordinates
if (ScreenManager.NormalizedToScreen(0, 0.5f, 0.5f, out int x, out int y))
{
    Console.WriteLine($"Center of screen 0: ({x}, {y})");
}
```

### Laser Pointer on Specific Screen

When laser pointer mode is activated, it will display only on the target screen:

```csharp
// Set target screen first
controller.TargetScreenIndex = 1;

// Then activate laser mode - it will appear on screen 1
controller.ToggleLaserMode();
```

## AprilTag Support for Camera Calibration

The system includes AprilTag 16h5 format markers for camera-based screen detection.

### AprilTag Concept

AprilTags are visual fiducial markers used for:
- Camera calibration and screen identification
- Determining which screen the camera is looking at
- Accurate coordinate mapping between camera and screen space

### AprilTag ID Mapping

Each screen displays 4 AprilTags (one per corner):
- **Screen 0**: Tags 0, 1, 2, 3
- **Screen 1**: Tags 4, 5, 6, 7
- **Screen 2**: Tags 8, 9, 10, 11
- And so on...

Corner positions:
- **Tag 0, 4, 8...** = Top-Left (TL)
- **Tag 1, 5, 9...** = Top-Right (TR)
- **Tag 2, 6, 10...** = Bottom-Right (BR)
- **Tag 3, 7, 11...** = Bottom-Left (BL)

### Using the Multi-Screen AprilTag Manager

```csharp
using TestOnRemoteControl.GestureControl;

// Create the manager
var aprilTagManager = new MultiScreenAprilTagManager
{
    TagSize = 120,       // Size in pixels
    CornerMargin = 30    // Distance from corners
};

// Show AprilTags on all screens
aprilTagManager.ShowAll();

// Or show on a specific screen
aprilTagManager.ShowOnScreen(0);

// Hide all
aprilTagManager.HideAll();

// Configure custom screen mapping
// (e.g., if your camera sees screens in a different order)
aprilTagManager.SetScreenMapping(physicalScreenIndex: 0, logicalScreenNumber: 1);
aprilTagManager.SetScreenMapping(physicalScreenIndex: 1, logicalScreenNumber: 0);

// Cleanup
aprilTagManager.Dispose();
```

### Screen Configuration Window

Use the **"Configure Screens"** button to:
1. View all connected displays
2. Assign logical screen numbers to physical displays
3. Preview AprilTags on each screen
4. Customize the tag ID mapping

### Detecting AprilTags in Python

Use the `apriltag` library in your CV module:

```python
import cv2
import apriltag

# Create detector for 16h5 family
options = apriltag.DetectorOptions(families="tag16h5")
detector = apriltag.Detector(options)

# Detect tags in frame
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
tags = detector.detect(gray)

for tag in tags:
    tag_id = tag.tag_id
    corners = tag.corners  # 4 corner points
    center = tag.center    # Center point
    
    # Determine which screen and corner
    screen_number = tag_id // 4
    corner_index = tag_id % 4  # 0=TL, 1=TR, 2=BR, 3=BL
    
    print(f"Tag {tag_id}: Screen {screen_number}, Corner {corner_index}")
```

### Multi-Device / Multi-Controller Setup

When controlling multiple devices:

1. **Device ID Filtering**: Use `deviceId` in your JSON packets:
   ```json
   {
       "type": "pointer",
       "deviceId": "device_1",
       "screenIndex": 0,
       "x": 0.5,
       "y": 0.5
   }
   ```

2. **Configure the receiver**:
   ```csharp
   receiver.DeviceIdFilter = "device_1";  // Only accept from this device
   receiver.ScreenIndexFilter = 0;         // Only accept for screen 0
   ```

3. **Ignore non-matching gestures**: The receiver automatically filters out gestures that don't match the configured filters.


