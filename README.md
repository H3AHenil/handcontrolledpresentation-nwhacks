# AprilTag Screen Registration

Camera-to-screen coordinate mapping using AprilTag markers and homography transformation.

## Overview

This system enables real-time pointer tracking by:

1. **Detecting AprilTags** (tag36h11 family) placed at the four corners of a monitor
2. **Computing a Homography Matrix** that maps the camera's perspective view (trapezoid) to screen coordinates (rectangle)
3. **Transforming coordinates** from camera space to screen pixel positions

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Generate printable AprilTag markers
python generate_tags.py
```

## Tag Placement

Print `tags/all_tags_printable.png` and place the tags at your monitor corners:

```
┌─────────────────────────────────┐
│ [ID 0]                   [ID 1] │
│  TL                         TR  │
│                                 │
│                                 │
│                                 │
│ [ID 3]                   [ID 2] │
│  BL                         BR  │
└─────────────────────────────────┘
```

## Usage

### Interactive Demo

```bash
python apriltag_screen.py
```

- Shows camera feed with detected tags highlighted
- Move mouse over window to see mapped screen coordinates
- Press `c` to lock/unlock calibration
- Press `q` to quit

### As a Module

```python
from apriltag_screen import AprilTagScreenMapper, ScreenConfig

# Configure for your screen
config = ScreenConfig(width=1920, height=1080)
mapper = AprilTagScreenMapper(config)

# Process a camera frame
tag_centers = mapper.detect_tags(frame)
if mapper.compute_homography(tag_centers):
    # Map any camera point to screen coordinates
    screen_x, screen_y = mapper.camera_to_screen((cam_x, cam_y))
```

## How It Works

### 1. AprilTag Detection
The `pupil-apriltags` library detects tag36h11 markers and returns their center coordinates in the camera frame.

### 2. Homography Calculation
Given 4 corresponding point pairs:
- **Source**: Tag centers in camera frame (forms a trapezoid due to perspective)
- **Destination**: Screen corner coordinates (perfect rectangle)

We compute a 3×3 homography matrix `H` using `cv2.findHomography()`:

```
[x']   [h11 h12 h13] [x]
[y'] = [h21 h22 h23] [y]
[w']   [h31 h32 h33] [1]

screen_x = x' / w'
screen_y = y' / w'
```

### 3. Coordinate Transformation
For any point `(x, y)` in the camera frame:
1. Convert to homogeneous coordinates: `[x, y, 1]`
2. Multiply by homography matrix
3. Divide by `w'` to get screen coordinates
