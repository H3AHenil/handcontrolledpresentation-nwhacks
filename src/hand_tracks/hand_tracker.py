"""MediaPipe hand tracking wrapper."""

import cv2
import mediapipe as mp
import numpy as np
from numpy.typing import NDArray


INDEX_FINGER_TIP = 8


class HandTracker:
    """Wrapper for MediaPipe hand tracking."""

    def __init__(
        self,
        max_num_hands: int = 1,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.7,
    ):
        self._mp_hands = mp.solutions.hands
        self._mp_draw = mp.solutions.drawing_utils
        self._hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._last_results = None

    def process(self, frame: NDArray[np.uint8]) -> None:
        """Process frame for hand detection."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._last_results = self._hands.process(rgb)

    def get_index_finger_tip(self, frame: NDArray[np.uint8]) -> tuple[int, int] | None:
        """Get index finger tip position from last processed frame."""
        self.process(frame)
        
        if not self._last_results or not self._last_results.multi_hand_landmarks:
            return None

        hand = self._last_results.multi_hand_landmarks[0]
        lm = hand.landmark[INDEX_FINGER_TIP]

        h, w = frame.shape[:2]
        return int(lm.x * w), int(lm.y * h)

    def draw_landmarks(self, frame: NDArray[np.uint8]) -> None:
        """Draw hand landmarks on frame."""
        if not self._last_results or not self._last_results.multi_hand_landmarks:
            return

        for hand in self._last_results.multi_hand_landmarks:
            self._mp_draw.draw_landmarks(
                frame, hand, self._mp_hands.HAND_CONNECTIONS
            )

    def close(self) -> None:
        """Release resources."""
        self._hands.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
