"""
Example: Integrating RAG Client with Hand Tracking Image Test
Shows how to use RAG to fetch images from database and display with hand gestures
"""

import cv2
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from GestureDetection.rag_client import RAGImageRetriever, InteractiveImageGallery
from GestureDetection.HandGestures import (
    detect_pinch_gesture,
    select_image,
    move_selected_image,
    release_image,
    classify_gesture
)
from GestureDetection.HandRecognition import detect_hand_gesture
import mediapipe as mp


class RAGIntegratedHandTracking:
    """
    Integrated system combining RAG database retrieval with hand gesture control.
    Fetches images from database after search and displays them with hand tracking.
    """
    
    def __init__(self, search_query: str = "home objects", limit: int = 5, 
                 width: int = 1280, height: int = 720):
        """
        Initialize RAG-integrated hand tracking.
        
        Args:
            search_query: Database search query
            limit: Number of images to retrieve
            width: Display width
            height: Display height
        """
        self.search_query = search_query
        self.limit = limit
        self.width = width
        self.height = height
        
        # Initialize RAG retriever
        print("Initializing RAG retriever...")
        self.rag_retriever = RAGImageRetriever(use_gemini=True)
        
        # Initialize hand tracking
        print("Initializing hand tracking...")
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # Gallery state
        self.gallery_images = []
        self.selected_image = None
        self.pinch_state = False
    
    def fetch_images_from_database(self) -> bool:
        """
        Fetch images from database using search query.
        
        Returns:
            True if images loaded successfully
        """
        print(f"\nSearching database for: '{self.search_query}'")
        print("-" * 50)
        
        # Search database
        search_results = self.rag_retriever.search_images_by_query(
            self.search_query, 
            limit=self.limit
        )
        
        if not search_results:
            print("✗ No images found in database")
            return False
        
        print(f"✓ Found {len(search_results)} results\n")
        
        # Load images and prepare for display
        self.gallery_images = []
        thumb_size = (150, 150)
        grid_cols = 3
        x_spacing = 200
        y_spacing = 200
        start_x = 50
        start_y = 150
        
        for idx, db_result in enumerate(search_results):
            print(f"Loading image {idx + 1}/{len(search_results)}: {db_result.get('name', 'Unknown')}")
            
            # Get image path from database result
            image_path = db_result.get('path')
            image_name = db_result.get('name', f'Image_{idx}')
            image_id = db_result.get('id', -1)
            
            # Load image file
            image_data = self.rag_retriever.load_image_file(image_path)
            
            if image_data is not None:
                # Resize to thumbnail
                image_data = cv2.resize(image_data, thumb_size)
                
                # Calculate grid position
                col = idx % grid_cols
                row = idx // grid_cols
                x = start_x + (col * x_spacing)
                y = start_y + (row * y_spacing)
                
                # Create gallery item
                gallery_item = {
                    "image": image_data,
                    "name": image_name,
                    "path": image_path,
                    "id": image_id,
                    "metadata": db_result,
                    "x": x,
                    "y": y,
                    "w": thumb_size[0],
                    "h": thumb_size[1],
                    "grabbed": False
                }
                self.gallery_images.append(gallery_item)
                print(f"  ✓ {image_name} (ID: {image_id})")
            else:
                print(f"  ✗ Failed to load {image_name}")
        
        print("\n" + "=" * 50)
        print(f"Gallery initialized with {len(self.gallery_images)} images")
        print("=" * 50 + "\n")
        
        return len(self.gallery_images) > 0
    
    def detect_hand_and_gesture(self, frame: np.ndarray):
        """
        Detect hand landmarks and classify gesture.
        
        Returns:
            Tuple: (index_pos, is_pinching, gesture_name, frame_with_skeleton)
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)
        
        index_pos = (0, 0)
        is_pinching = False
        gesture = "No Hand"
        
        if results.multi_hand_landmarks:
            for hand_lms, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                # Draw hand skeleton
                self.mp_draw.draw_landmarks(frame, hand_lms, self.mp_hands.HAND_CONNECTIONS)
                
                # Detect pinch gesture
                is_pinching, index_pos, thumb_pos = detect_pinch_gesture(
                    hand_lms, self.width, self.height, threshold=50
                )
                
                # Classify gesture
                gesture = classify_gesture(hand_lms.landmark, handedness.classification[0].label)
                
                # Draw hand position indicator
                if is_pinching:
                    cv2.circle(frame, index_pos, 12, (0, 0, 255), -1)  # Red when pinching
                else:
                    cv2.circle(frame, index_pos, 8, (0, 255, 0), -1)   # Green when not pinching
        
        return index_pos, is_pinching, gesture, frame
    
    def render_gallery_on_frame(self, frame: np.ndarray, index_pos, gesture, is_pinching) -> np.ndarray:
        """
        Draw gallery images and UI on frame.
        
        Args:
            frame: Input frame
            index_pos: Hand index finger position
            gesture: Current gesture name
            is_pinching: Whether pinching
        
        Returns:
            Annotated frame
        """
        # Draw background for status area
        cv2.rectangle(frame, (0, 0), (self.width, 120), (20, 20, 20), -1)
        
        # Draw all gallery images
        for img_item in self.gallery_images:
            # Get image region
            x, y, w, h = img_item['x'], img_item['y'], img_item['w'], img_item['h']
            
            # Clip to frame bounds
            y1 = max(0, y)
            y2 = min(self.height, y + h)
            x1 = max(0, x)
            x2 = min(self.width, x + w)
            
            if y2 > y1 and x2 > x1:
                # Draw image on frame
                frame[y1:y2, x1:x2] = img_item['image'][:y2-y1, :x2-x1]
            
            # Draw border (highlight if selected)
            border_color = (0, 255, 255) if img_item['grabbed'] else (100, 100, 100)
            border_thickness = 3 if img_item['grabbed'] else 2
            cv2.rectangle(frame, (x, y), (x + w, y + h), border_color, border_thickness)
            
            # Draw image name label
            label = f"{img_item['name'][:12]}"
            cv2.putText(frame, label, (x + 5, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            
            # Draw image ID if selected
            if img_item['grabbed']:
                cv2.putText(frame, f"ID: {img_item['id']}", (x + 5, y + h + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        # Draw status information
        cv2.putText(frame, f"Query: {self.search_query}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        gesture_color = (0, 0, 255) if gesture != "No Hand" else (100, 100, 100)
        cv2.putText(frame, f"Gesture: {gesture}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, gesture_color, 2)
        
        status = "PINCHING" if is_pinching else "Ready"
        status_color = (0, 0, 255) if is_pinching else (0, 255, 0)
        cv2.putText(frame, f"Status: {status}", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        # Draw controls hint
        hint = "Pinch to grab | Move to drag | Release to drop | ESC to exit"
        cv2.putText(frame, hint, (10, self.height - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        return frame
    
    def run(self):
        """Main execution loop"""
        # Fetch images from database
        if not self.fetch_images_from_database():
            print("Failed to load images from database")
            return
        
        # Initialize camera
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("✗ Cannot open camera")
            return
        
        print("✓ Camera initialized")
        print("\n=== Interactive Gallery with Hand Gestures ===")
        print("Commands:")
        print("  • Pinch (thumb + index close): Select and grab image")
        print("  • Move hand while pinching: Drag image")
        print("  • Release pinch: Drop image")
        print("  • ESC: Exit")
        print("=" * 45 + "\n")
        
        prev_time = 0
        fps = 0
        
        try:
            while True:
                success, frame = cap.read()
                if not success:
                    print("Failed to read from camera")
                    break
                
                # Mirror for better UX
                frame = cv2.flip(frame, 1)
                h, w = frame.shape[:2]
                self.width = w
                self.height = h
                
                # Detect hand and gesture
                index_pos, is_pinching, gesture, frame = self.detect_hand_and_gesture(frame)
                
                # Handle pinch-based image selection and movement
                if is_pinching and not self.pinch_state:
                    # Start pinch
                    self.selected_image = select_image(index_pos, self.gallery_images)
                    self.pinch_state = True
                    if self.selected_image:
                        print(f"Selected: {self.selected_image['name']}")
                
                elif is_pinching and self.selected_image:
                    # Continue pinching - move image
                    move_selected_image(index_pos, self.selected_image)
                
                elif not is_pinching and self.pinch_state:
                    # Release pinch
                    if self.selected_image:
                        print(f"Released: {self.selected_image['name']}")
                    self.selected_image = release_image(self.selected_image)
                    self.pinch_state = False
                
                # Render gallery
                frame = self.render_gallery_on_frame(frame, index_pos, gesture, is_pinching)
                
                # Calculate and display FPS
                current_time = cv2.getTickCount() / cv2.getTickFrequency()
                if prev_time != 0:
                    fps = 1 / (current_time - prev_time)
                prev_time = current_time
                
                cv2.putText(frame, f"FPS: {fps:.1f}", (self.width - 180, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Display
                cv2.imshow("RAG Image Gallery - Hand Gesture Control", frame)
                
                # Exit on ESC
                if cv2.waitKey(1) & 0xFF == 27:
                    print("\nExiting gallery...")
                    break
        
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        
        finally:
            # Cleanup
            cap.release()
            self.hands.close()
            cv2.destroyAllWindows()
            print("✓ Resources cleaned up")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="RAG-Integrated Hand Tracking with Database Images"
    )
    parser.add_argument("--query", type=str, default="home objects",
                       help="Search query for database (default: 'home objects')")
    parser.add_argument("--limit", type=int, default=5,
                       help="Number of images to retrieve (default: 5)")
    parser.add_argument("--width", type=int, default=1280,
                       help="Display width (default: 1280)")
    parser.add_argument("--height", type=int, default=720,
                       help="Display height (default: 720)")
    
    args = parser.parse_args()
    
    # Run integrated system
    system = RAGIntegratedHandTracking(
        search_query=args.query,
        limit=args.limit,
        width=args.width,
        height=args.height
    )
    system.run()
