"""
Finger-to-Screen Coordinate Tracker

Integrates AprilTag screen detection with MediaPipe hand tracking.
Maps finger position to screen coordinates using perspective-correct homography.
"""

import cv2

from apriltage import CAMERA_WIDTH, CAMERA_HEIGHT
from src.hand_tracks import HandTracker, MultiScreenMapper, TrackerDisplay


INSTRUCTIONS = """
==================================================
Finger-to-Screen Coordinate Tracker
==================================================

Place AprilTags at screen corners:
  Screen 0: IDs 0-3   (0=TL, 1=TR, 2=BR, 3=BL)
  Screen 1: IDs 4-7   (4=TL, 5=TR, 6=BR, 7=BL)

Point your index finger at the screen to see coordinates.

Controls:
  'q' or ESC - Quit
"""


def run_finger_tracker(camera_index: int = 0) -> None:
    """Run the finger-to-screen coordinate tracker."""
    print(INSTRUCTIONS)

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Error: Cannot open camera {camera_index}")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    with HandTracker() as tracker, TrackerDisplay() as display:
        mapper = MultiScreenMapper()

        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            mapper.update(frame)
            finger_pos = tracker.get_index_finger_tip(frame)
            screen_result = mapper.find_screen(*finger_pos) if finger_pos else None

            tracker.draw_landmarks(frame)
            display.render(frame, mapper, finger_pos, screen_result)

            key = display.show(frame)
            if key in (ord("q"), 27):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Finger-to-Screen Coordinate Tracker")
    parser.add_argument("-c", "--camera", type=int, default=0, help="Camera index")
    args = parser.parse_args()

    run_finger_tracker(camera_index=args.camera)
