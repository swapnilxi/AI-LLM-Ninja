# handGesture_core/test_handtracking.py

import cv2
import mediapipe as mp
from pathlib import Path
import importlib.util

# Prefer direct package import (works if project root is on PYTHONPATH)
try:
    from GestureDetection.camera_and_input_layer import InputLayer
except Exception:
    # Fallback: load module by file path relative to this test file
    repo_root = Path(__file__).resolve().parents[1]  # visionrag-backend
    module_path = repo_root / "GestureDetection" / "camera_and_input_layer.py"
    spec = importlib.util.spec_from_file_location("camera_and_input_layer", str(module_path))
    cam_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cam_mod)
    InputLayer = cam_mod.InputLayer

"""
Test 2:
Runs MediaPipe hand tracking on top of camera / fallback frames.

This confirms:
- MediaPipe is installed correctly
- InputLayer returns frames
- Hand skeleton is drawn
"""

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

def main():
    inp = InputLayer("fallback.jpg")

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    )

    while True:
        frame, src = inp.get_frame()

        # Convert BGR → RGB for MediaPipe
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        # Draw landmarks
        if result.multi_hand_landmarks:
            for handLms in result.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, handLms, mp_hands.HAND_CONNECTIONS)

        # Show camera/fallback status
        cv2.putText(frame, f"Source: {src}", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        cv2.imshow("Hand Tracking Test", frame)

        # Close with ESC
        if cv2.waitKey(1) & 0xFF == 27:
            break

    hands.close()
    inp.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
