# handGesture_core/handtracking_image_tests.py

import cv2
import mediapipe as mp
import numpy as np
from pathlib import Path
import importlib.util

# Try direct package import first (works when project root is on PYTHONPATH)
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

# Try to import utility; if unavailable provide a simple fallback
try:
    from core.utils import is_inside_box
except Exception:
    def is_inside_box(px, py, x, y, w, h):
        """Simple box containment helper fallback.

        px,py: point coordinates
        x,y,w,h: box origin and size
        """
        return (x <= px <= x + w) and (y <= py <= y + h)

# MediaPipe Hand Tracking Setup
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

# Image for testing
IMAGE_PATH = "fallback.jpg"  # Change this to any image you'd like to move

class HandTrackingImageTest:
    def __init__(self, image_path, width=1280, height=720):
        self.image_path = image_path
        self.width = width
        self.height = height

        # Initialize Input Layer (camera + fallback)
        self.input_layer = InputLayer(self.image_path, desired_width=self.width, desired_height=self.height)

        # Load images to be draggable
        self.images = self.load_images()

        # Initialize hand tracking
        self.hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        )

        self.selected_image = None
        self.index_finger_pos = (0, 0)  # Current index finger position
        self.pinch_down = False  # Track pinch state for deselection

    def load_images(self):
        """Load images to move on the canvas."""
        img = cv2.imread(self.image_path)
        img = cv2.resize(img, (150, 150))

        images = []
        for i in range(3):  # Test with 3 images
            img_copy = img.copy()
            images.append({
                "image": img_copy,
                "x": np.random.randint(50, self.width-150),
                "y": np.random.randint(50, self.height-150),
                "w": 150,
                "h": 150,
                "grabbed": False
            })
        return images

    def detect_hand_gesture(self, frame):
        """Detect hand position and pinch gesture.
        Returns: (index_finger_pos, is_pinching)
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.hands.process(rgb)
        pinch = False
        index_pos = (0, 0)

        if result.multi_hand_landmarks:
            for hand_landmarks in result.multi_hand_landmarks:
                # Draw hand landmarks
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                # Get thumb and index finger positions
                index_finger = hand_landmarks.landmark[8]
                thumb_finger = hand_landmarks.landmark[4]

                ix, iy = int(index_finger.x * self.width), int(index_finger.y * self.height)
                tx, ty = int(thumb_finger.x * self.width), int(thumb_finger.y * self.height)
                index_pos = (ix, iy)

                # Detect pinch gesture (close distance between thumb and index)
                dist = np.hypot(ix - tx, iy - ty)
                if dist < 50:  # Pinch threshold
                    pinch = True

        return index_pos, pinch

    def move_selected_image(self, pointer):
        """Move the selected image according to hand pointer."""
        if self.selected_image is not None:
            self.selected_image["x"] = pointer[0] - self.selected_image["w"] // 2
            self.selected_image["y"] = pointer[1] - self.selected_image["h"] // 2

    def select_image(self, pointer):
        """Select an image with pinch gesture."""
        for img in self.images:
            if is_inside_box(pointer[0], pointer[1], img["x"], img["y"], img["w"], img["h"]):
                self.selected_image = img
                img["grabbed"] = True
                break

    def release_image(self):
        """Release selected image."""
        if self.selected_image is not None:
            self.selected_image["grabbed"] = False
            self.selected_image = None

    def run(self):
        while True:
            frame, source = self.input_layer.get_frame()

            index_pos, pinch = self.detect_hand_gesture(frame)
            self.index_finger_pos = index_pos

            # Selection: Index finger overlaps with an image
            if self.selected_image is None:
                self.select_image(index_pos)

            # If already selected, move image with index finger
            if self.selected_image is not None:
                self.move_selected_image(index_pos)
                # Deselection: Pinch gesture releases the image
                if pinch and not self.pinch_down:
                    self.pinch_down = True
                if not pinch and self.pinch_down:
                    self.pinch_down = False
                    self.release_image()

            # Draw all images (draggable)
            for img in self.images:
                overlay = cv2.resize(img["image"], (img["w"], img["h"]))
                # Clip to frame bounds to avoid overflow
                y1, y2 = max(0, img["y"]), min(self.height, img["y"] + img["h"])
                x1, x2 = max(0, img["x"]), min(self.width, img["x"] + img["w"])
                overlay_y1 = max(0, -img["y"])
                overlay_x1 = max(0, -img["x"])
                overlay_y2 = overlay_y1 + (y2 - y1)
                overlay_x2 = overlay_x1 + (x2 - x1)
                if y2 > y1 and x2 > x1:
                    frame[y1:y2, x1:x2] = overlay[overlay_y1:overlay_y2, overlay_x1:overlay_x2]
                # Draw selection box if grabbed
                if img["grabbed"]:
                    cv2.rectangle(frame, (img["x"], img["y"]), (img["x"] + img["w"], img["y"] + img["h"]), (0, 255, 255), 2)

            # Display source overlay
            cv2.putText(frame, f"Source: {source}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            if self.selected_image is not None:
                status_text = "SELECTED - Pinch to deselect"
                color = (0, 255, 255)
            else:
                status_text = "Move index finger over image to select"
                color = (0, 165, 255)
            cv2.putText(frame, status_text, (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            # Draw index finger position as a circle
            cv2.circle(frame, index_pos, 5, (255, 0, 0), -1)

            # Show frame
            cv2.imshow("Hand Tracking Image Test", frame)

            # Exit on ESC
            if cv2.waitKey(1) & 0xFF == 27:
                break

        self.hands.close()
        self.input_layer.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    test = HandTrackingImageTest("fallback.jpg")
    test.run()
