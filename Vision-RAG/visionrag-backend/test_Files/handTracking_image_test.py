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
# List of image names to load from 'images' folder
IMAGE_PATHS = ["image1.jpg", "image2.jpg", "image3.jpg"]  # Add your image filenames here

class HandTrackingImageTest:
    def __init__(self, image_names, width=1280, height=720):
        """
        Args:
            image_names: List of image filenames to load from 'images' folder
                        Example: ["image1.jpg", "image2.png", "image3.jpg"]
            width: Frame width
            height: Frame height
        """
        self.image_names = image_names if isinstance(image_names, list) else [image_names]
        self.width = width
        self.height = height

        # Initialize Input Layer (camera + fallback)
        self.input_layer = InputLayer("fallback.jpg", desired_width=self.width, desired_height=self.height)

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
        self.mouse_pos = (0, 0)  # Current mouse position
        self.mouse_down = False  # Track mouse button state for drag-and-drop

    def load_images(self):
        """Load images from the images folder using the image_names list.
        
        Tries to load from:
        1. Image names specified in IMAGE_PATHS list from 'images' folder (for testing)
        2. Falls back to creating variations of the fallback image
        
        TODO: Replace with database query (commented below)
        """
        images = []
        test_dir = Path(__file__).parent
        images_dir = test_dir / "images"
        
        # ============== TESTING: Load from images folder using image_names list ==============
        for img_name in self.image_names:
            img_path = images_dir / img_name
            if img_path.exists():
                img = cv2.imread(str(img_path))
                if img is not None:
                    img = cv2.resize(img, (150, 150))
                    images.append({
                        "image": img,
                        "path": str(img_path),  # Store file path for reference
                        "name": img_name,  # Store image name
                        "x": np.random.randint(50, self.width-150),
                        "y": np.random.randint(50, self.height-150),
                        "w": 150,
                        "h": 150,
                        "grabbed": False
                    })
            else:
                print(f"Warning: Image not found at {img_path}")
        
        # ============== DATABASE: Fetch image paths from DB ==============
        # TODO: Uncomment this section when ready to use database
        """
        # Example: Query database for image paths
        # from your_db_module import get_image_paths
        
        # image_data = get_image_paths()  # Returns list of dicts: [{'path': '/path/to/image.jpg', 'id': 123, 'name': 'img1'}, ...]
        # for data in image_data:  # Load all images from DB
        #     img = cv2.imread(data['path'])
        #     if img is not None:
        #         img = cv2.resize(img, (150, 150))
        #         images.append({
        #             "image": img,
        #             "path": data['path'],  # Store file path
        #             "name": data.get('name'),  # Store image name
        #             "db_id": data.get('id'),  # Store DB ID if needed
        #             "x": np.random.randint(50, self.width-150),
        #             "y": np.random.randint(50, self.height-150),
        #             "w": 150,
        #             "h": 150,
        #             "grabbed": False
        #         })
        """
        
        # If no images found, create 3 variations of fallback image with different colors
        if len(images) == 0:
            print("No images loaded from list. Creating fallback variations...")
            base_img = cv2.imread(str(Path(__file__).parent / "fallback.jpg"))
            if base_img is not None:
                base_img = cv2.resize(base_img, (150, 150))
                
                # Create 3 variations with different color channels
                variations = [
                    base_img.copy(),  # Original
                    cv2.cvtColor(cv2.cvtColor(base_img, cv2.COLOR_BGR2HSV), cv2.COLOR_HSV2BGR),  # Color shifted
                    cv2.cvtColor(base_img, cv2.COLOR_BGR2GRAY)  # Grayscale (expand to 3 channels)
                ]
                
                # Convert grayscale to 3-channel
                if len(variations[2].shape) == 2:
                    variations[2] = cv2.cvtColor(variations[2], cv2.COLOR_GRAY2BGR)
                
                for idx, var_img in enumerate(variations):
                    images.append({
                        "image": var_img,
                        "path": f"fallback_variation_{idx}",  # Placeholder path
                        "name": f"fallback_variation_{idx}",  # Placeholder name
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

    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for fallback control when camera unavailable."""
        self.mouse_pos = (x, y)
        
        # Left mouse button down = select/drag
        if event == cv2.EVENT_LBUTTONDOWN:
            self.mouse_down = True
            if self.selected_image is None:
                self.select_image((x, y))
        
        # Left mouse button released = deselect
        elif event == cv2.EVENT_LBUTTONUP:
            self.mouse_down = False
            self.release_image()
        
        # Mouse move while button pressed = drag
        elif event == cv2.EVENT_MOUSEMOVE and self.mouse_down and self.selected_image is not None:
            self.move_selected_image((x, y))

    def run(self):
        while True:
            frame, source = self.input_layer.get_frame()

            index_pos, pinch = self.detect_hand_gesture(frame)
            self.index_finger_pos = index_pos

            # Determine control source: hand gesture or mouse fallback
            use_hand_control = source == "camera"  # Use hand control only if camera is active
            
            if use_hand_control:
                # ============== HAND GESTURE CONTROL ==============
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
            else:
                # ============== MOUSE FALLBACK CONTROL ==============
                # Mouse callback will handle selection/movement/release
                pass

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
                status_text = "SELECTED - "
                if use_hand_control:
                    status_text += "Pinch to deselect"
                else:
                    status_text += "Release mouse to deselect"
                color = (0, 255, 255)
            else:
                if use_hand_control:
                    status_text = "Move index finger over image to select"
                else:
                    status_text = "Click on image to select (mouse mode)"
                color = (0, 165, 255)
            cv2.putText(frame, status_text, (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # Draw index finger position as a circle (hand control only)
            if use_hand_control:
                cv2.circle(frame, index_pos, 5, (255, 0, 0), -1)
            else:
                # Draw mouse cursor circle (mouse control)
                cv2.circle(frame, self.mouse_pos, 5, (255, 255, 0), -1)

            # Show frame
            cv2.imshow("Hand Tracking Image Test", frame)
            
            # Set up mouse callback for fallback control
            cv2.setMouseCallback("Hand Tracking Image Test", self.mouse_callback)

            # Exit on ESC
            if cv2.waitKey(1) & 0xFF == 27:
                break

        self.hands.close()
        self.input_layer.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # Pass the list of image names to load from 'images' folder
    test = HandTrackingImageTest(IMAGE_PATHS)
    test.run()
