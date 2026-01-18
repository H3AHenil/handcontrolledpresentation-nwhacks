import cv2
import mediapipe as mp
import pyautogui
import threading


import numpy as np

def finger_to_coordinate(box: tuple[int, int, int, int], finger_coord: tuple[int, int]):
    """
    box: (x1, y1, x2, y2)
    finger_coord: (finger_x, finger_y)

    Returns:
        (rel_x, rel_y) in [0,1] or (-1,-1) if outside
    """
    x1, y1, x2, y2 = box
    fx, fy = finger_coord
    if x1 <= fx <= x2 and y1 <= fy <= y2:
        rel_x = (fx - x1) / (x2 - x1)
        rel_y = (fy - y1) / (y2 - y1)
        return rel_x, rel_y
    else:
        return -1, -1



mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

cap = cv2.VideoCapture(0)
cv2.namedWindow("Purple Box Touch Test", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Purple Box Touch Test", 960, 720)

# ==============================
# Main loop
# ==============================
try:
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        frame_height, frame_width, _ = frame.shape

        # Purple box
        box_margin = 100
        x1, y1 = box_margin, box_margin
        x2, y2 = frame_width - box_margin, frame_height - box_margin
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)

        box = (x1, y1, x2, y2)

        if results.multi_hand_landmarks:
            hand = results.multi_hand_landmarks[0]
            lm = hand.landmark

            mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

            finger_x = int(lm[8].x * frame_width)
            finger_y = int(lm[8].y * frame_height)

            # Compute relative coordinates
            rel_x, rel_y = finger_to_coordinate(box, (finger_x, finger_y))

            # Visualization
            cv2.circle(frame, (finger_x, finger_y), 10, (0, 255, 0), -1)

            cv2.putText(
                frame,
                f"Relative: ({rel_x:.2f}, {rel_y:.2f})",
                (50, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

        cv2.imshow("Purple Box Touch Test", frame)

        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            break

finally:
    cap.release()
    cv2.destroyAllWindows()