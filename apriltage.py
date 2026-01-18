"""
AprilTag Screen Registration with Homography Mapping (tag16h5)

Screen Registration:
- Detects 4 AprilTags (IDs 0-3) at screen corners
- Tags act as anchors for position/orientation tracking

Inverse Perspective Mapping:
- Camera sees screen as trapezoid (due to viewing angle)
- Homography matrix "un-warps" trapezoid → rectangle
- Maps any camera pixel to actual screen coordinates
"""

import cv2
import numpy as np

# Screen configuration
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

# Tag IDs for each corner: [top-left, top-right, bottom-right, bottom-left]
CORNER_TAG_IDS = [0, 1, 2, 3]

# AprilTag corner indices (counter-clockwise from bottom-left)
CORNER_BL, CORNER_BR, CORNER_TR, CORNER_TL = 0, 1, 2, 3

# Which corner of each tag faces the screen center (inner corner)
INNER_CORNER = {
    0: CORNER_BR,  # Top-left tag → use bottom-right corner
    1: CORNER_BL,  # Top-right tag → use bottom-left corner
    2: CORNER_TL,  # Bottom-right tag → use top-left corner
    3: CORNER_TR,  # Bottom-left tag → use top-right corner
}


class ScreenMapper:
    """Maps camera coordinates to screen coordinates using AprilTag homography."""

    def __init__(self, screen_width: int = SCREEN_WIDTH, screen_height: int = SCREEN_HEIGHT):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Destination points (screen corners)
        self.screen_corners = np.array([
            [0, 0],                              # Top-left
            [screen_width - 1, 0],               # Top-right
            [screen_width - 1, screen_height - 1],  # Bottom-right
            [0, screen_height - 1],              # Bottom-left
        ], dtype=np.float32)

        self.homography = None
        self.inverse_homography = None
        self.camera_corners = None  # Detected tag corners in camera frame

    def update(self, tag_corners: dict[int, np.ndarray]) -> bool:
        """
        Update homography from detected tag corners.

        Args:
            tag_corners: Dict mapping tag_id -> 4 corner points

        Returns:
            True if homography was computed (all 4 tags detected)
        """
        # Check all 4 corner tags are detected
        if not all(tid in tag_corners for tid in CORNER_TAG_IDS):
            return False

        # Extract inner corners (the corner facing screen center)
        src_points = []
        for tag_id in CORNER_TAG_IDS:
            corners = tag_corners[tag_id]
            inner_idx = INNER_CORNER[tag_id]
            src_points.append(corners[inner_idx])

        self.camera_corners = np.array(src_points, dtype=np.float32)

        # Compute homography: camera → screen
        self.homography = cv2.getPerspectiveTransform(
            self.camera_corners, self.screen_corners
        )
        self.inverse_homography = cv2.getPerspectiveTransform(
            self.screen_corners, self.camera_corners
        )

        return True

    def camera_to_screen(self, x: float, y: float) -> tuple[int, int] | None:
        """
        Map camera pixel to screen pixel.

        Input: (x, y) in camera frame (the trapezoid)
        Output: (x, y) in screen coordinates (the rectangle)
        """
        if self.homography is None:
            return None

        pt = np.array([[[x, y]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.homography)

        sx = int(round(transformed[0, 0, 0]))
        sy = int(round(transformed[0, 0, 1]))
        return (sx, sy)

    def screen_to_camera(self, x: float, y: float) -> tuple[int, int] | None:
        """Map screen pixel to camera pixel (inverse transform)."""
        if self.inverse_homography is None:
            return None

        pt = np.array([[[x, y]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, self.inverse_homography)

        cx = int(round(transformed[0, 0, 0]))
        cy = int(round(transformed[0, 0, 1]))
        return (cx, cy)

    def is_on_screen(self, sx: int, sy: int) -> bool:
        """Check if screen coordinates are within bounds."""
        return 0 <= sx < self.screen_width and 0 <= sy < self.screen_height

    @property
    def is_calibrated(self) -> bool:
        return self.homography is not None


def main():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Setup AprilTag detector (tag16h5)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_16h5)
    parameters = cv2.aruco.DetectorParameters()
    parameters.minMarkerPerimeterRate = 0.03
    parameters.errorCorrectionRate = 0.1
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    # Screen mapper
    mapper = ScreenMapper()

    print("=" * 50)
    print("AprilTag Screen Registration (tag16h5)")
    print("=" * 50)
    print("\nPlace tags at screen corners:")
    print("  ID 0: Top-left     ID 1: Top-right")
    print("  ID 3: Bottom-left  ID 2: Bottom-right")
    print("\nControls:")
    print("  'q' - Quit")
    print("  Mouse - Show mapped screen coordinates")
    print()

    mouse_pos = [None]

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_MOUSEMOVE:
            mouse_pos[0] = (x, y)

    cv2.namedWindow("AprilTag Screen Registration")
    cv2.setMouseCallback("AprilTag Screen Registration", on_mouse)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)

        # Build tag corners dict
        tag_corners = {}
        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                if marker_id in CORNER_TAG_IDS:
                    # corners[i] shape: (1, 4, 2) → squeeze to (4, 2)
                    tag_corners[marker_id] = corners[i].squeeze()

        # Update homography
        mapper.update(tag_corners)

        # Draw detected markers
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)

        # Draw inner corners (green) and screen quadrilateral (magenta)
        for tag_id, crns in tag_corners.items():
            inner_idx = INNER_CORNER[tag_id]
            ix, iy = int(crns[inner_idx][0]), int(crns[inner_idx][1])
            cv2.circle(frame, (ix, iy), 8, (0, 255, 0), -1)

        if mapper.camera_corners is not None:
            pts = mapper.camera_corners.astype(np.int32)
            cv2.polylines(frame, [pts], True, (255, 0, 255), 2)

        # Status
        if mapper.is_calibrated:
            cv2.putText(frame, "CALIBRATED", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        else:
            detected = list(tag_corners.keys())
            cv2.putText(frame, f"Detected: {detected} (need 0,1,2,3)", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Show mouse mapping
        if mouse_pos[0] and mapper.is_calibrated:
            mx, my = mouse_pos[0]
            screen_pt = mapper.camera_to_screen(mx, my)
            if screen_pt:
                sx, sy = screen_pt
                on_screen = mapper.is_on_screen(sx, sy)
                color = (0, 255, 0) if on_screen else (0, 165, 255)

                cv2.circle(frame, (mx, my), 6, color, -1)
                cv2.putText(frame, f"Screen: ({sx}, {sy})",
                           (mx + 10, my - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Show info
        h, w = frame.shape[:2]
        info = f"Camera: {w}x{h} | Screen: {mapper.screen_width}x{mapper.screen_height}"
        cv2.putText(frame, info, (10, h - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        cv2.imshow("AprilTag Screen Registration", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
