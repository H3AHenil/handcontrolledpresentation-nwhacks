import cv2
import mediapipe as mp
import pyautogui
import threading

# Setup
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

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0
screen_width, screen_height = pyautogui.size()


# Cursor thread for smooth movement
class CursorThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.x, self.y = pyautogui.position()
        self.tx, self.ty = self.x, self.y
        self.active = False
        self.running = True

    def run(self):
        while self.running:
            if self.active:
                dx = self.tx - self.x
                dy = self.ty - self.y
                self.x += dx * 0.2
                self.y += dy * 0.2
                pyautogui.moveTo(self.x, self.y, _pause=False)

    def update(self, x, y):
        self.tx, self.ty = x, y

cursor = CursorThread()
cursor.start()

# Main
try:
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        # purple box
        frame_height, frame_width, _ = frame.shape
        box_margin = 100
        x1, y1 = box_margin, box_margin
        x2, y2 = frame_width - box_margin, frame_height - box_margin
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)

        # Hand detection
        if results.multi_hand_landmarks:
            hand = results.multi_hand_landmarks[0]
            lm = hand.landmark

            mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

            finger_x = int(lm[8].x * frame_width)
            finger_y = int(lm[8].y * frame_height)

            # Check if finger is inside the purple box
            if x1 <= finger_x <= x2 and y1 <= finger_y <= y2:
                rel_x = (finger_x - x1) / (x2 - x1)
                rel_y = (finger_y - y1) / (y2 - y1)
            else:
                rel_x, rel_y = -1, -1  # outside box

            if rel_x != -1:
                screen_x = int((finger_x - x1) / (x2 - x1) * screen_width)
            else:
                screen_x = -1
            if rel_y != -1:
                screen_y = int((finger_y - y1) / (y2 - y1) * screen_height)
            else:
                screen_y = -1

            # Fingertip and coordinates
            cv2.circle(frame, (finger_x, finger_y), 10, (0, 255, 0), -1)
            cv2.putText(frame,
                        f"Relative: ({rel_x:.2f}, {rel_y:.2f})",
                        (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 0),
                        2)
            cv2.putText(frame,
                        f"Screen: ({screen_x}, {screen_y})",
                        (50, 100),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 0),
                        2)
        else:
            cursor.active = False

        # Show frame
        cv2.imshow("Purple Box Touch Test", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

finally:
    cursor.running = False
    cap.release()
    cv2.destroyAllWindows()
