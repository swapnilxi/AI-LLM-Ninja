"""
RAG Client for Vision-RAG System
Handles database queries, image retrieval, and integration with hand gesture recognition.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import os
import sys
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import RAG modules
try:
    from RAG_Module.retrieval_gemini import GeminiRetrieval
    from RAG_Module.retrieval_yolo import YOLORetrieval
    from RAG_Module.db import DatabaseConnection
    from RAG_Module.schemas import ImageData
except ImportError:
    print("Warning: RAG modules not available. Using mock implementations.")
    GeminiRetrieval = None
    YOLORetrieval = None
    DatabaseConnection = None
    ImageData = None

# Import Hand Gesture modules
from HandGestures import (
    detect_pinch_gesture,
    is_inside_box,
    select_image,
    move_selected_image,
    release_image,
    classify_gesture
)
from HandRecognition import detect_hand_gesture

# Import gesture utilities
from gesture_utils import (
    init_camera,
    mirror_frame,
    bgr_to_rgb,
    display_frame,
    close_camera_and_windows,
    FPSCounter,
    draw_rectangle,
    draw_text,
    draw_filled_circle,
    COLORS
)

class RAGImageRetriever:
    """
    Retrieves images from database based on search query.
    Integrates with RAG modules for semantic search.
    """
    
    def __init__(self, use_gemini=True, use_yolo=False):
        """
        Initialize RAG image retriever.
        
        Args:
            use_gemini: Use Gemini for semantic search
            use_yolo: Use YOLO for object detection-based search
        """
        self.use_gemini = use_gemini
        self.use_yolo = use_yolo
        self.db = self._init_database()
        self.gemini_retrieval = self._init_gemini() if use_gemini else None
        self.yolo_retrieval = self._init_yolo() if use_yolo else None
    
    def _init_database(self) -> Optional['DatabaseConnection']:
        """Initialize database connection"""
        try:
            if DatabaseConnection:
                return DatabaseConnection()
        except Exception as e:
            print(f"Database initialization failed: {e}")
        return None
    
    def _init_gemini(self) -> Optional['GeminiRetrieval']:
        """Initialize Gemini retrieval"""
        try:
            if GeminiRetrieval:
                return GeminiRetrieval()
        except Exception as e:
            print(f"Gemini initialization failed: {e}")
        return None
    
    def _init_yolo(self) -> Optional['YOLORetrieval']:
        """Initialize YOLO retrieval"""
        try:
            if YOLORetrieval:
                return YOLORetrieval()
        except Exception as e:
            print(f"YOLO initialization failed: {e}")
        return None
    
    def search_images_by_query(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search database for images matching query using Gemini semantic search.
        Falls back to demo mode if modules not available.
        
        Args:
            query: Search query string (e.g., "living room furniture")
            limit: Maximum number of results to return
        
        Returns:
            List of image dictionaries: [{'name': str, 'path': str, 'id': int, ...}, ...]
        """
        results = []
        
        try:
            if self.gemini_retrieval and self.db:
                # Use Gemini for semantic search
                embeddings = self.gemini_retrieval.embed_query(query)
                results = self.db.search_by_embedding(embeddings, limit=limit)
            else:
                # Fallback: use demo mode with sample images
                print("Using demo mode - searching for sample images")
                results = self._generate_demo_results(query, limit)
        except Exception as e:
            print(f"Error searching images: {e}")
            results = self._generate_demo_results(query, limit)
        
        return results
    
    def _generate_demo_results(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Generate demo/sample image results for testing without database.
        
        Args:
            query: Search query string
            limit: Number of results to generate
        
        Returns:
            List of sample image metadata
        """
        # Sample image paths - customize these to match your test images
        sample_images = [
            {
                'id': 1,
                'name': 'sample_1.jpg',
                'path': os.path.join(str(Path(__file__).parent), 'sample_images', 'sample_1.jpg'),
                'category': 'furniture'
            },
            {
                'id': 2,
                'name': 'sample_2.jpg',
                'path': os.path.join(str(Path(__file__).parent), 'sample_images', 'sample_2.jpg'),
                'category': 'furniture'
            },
            {
                'id': 3,
                'name': 'sample_3.jpg',
                'path': os.path.join(str(Path(__file__).parent), 'sample_images', 'sample_3.jpg'),
                'category': 'objects'
            },
            {
                'id': 4,
                'name': 'sample_4.jpg',
                'path': os.path.join(str(Path(__file__).parent), 'sample_images', 'sample_4.jpg'),
                'category': 'objects'
            },
            {
                'id': 5,
                'name': 'sample_5.jpg',
                'path': os.path.join(str(Path(__file__).parent), 'sample_images', 'sample_5.jpg'),
                'category': 'home'
            }
        ]
        
        return sample_images[:limit]
    
    def search_images_by_object(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search database for images containing specific objects using YOLO.
        
        Args:
            query: Object name to detect (e.g., "chair", "sofa")
            limit: Maximum number of results
        
        Returns:
            List of image dictionaries with detection metadata
        """
        results = []
        
        try:
            if self.yolo_retrieval and self.db:
                # Use YOLO for object-based search
                results = self.db.search_by_object(query, limit=limit)
                # Filter by YOLO detection confidence
                results = self.yolo_retrieval.filter_by_detection(results, confidence=0.6)
            else:
                print("YOLO or Database not initialized")
        except Exception as e:
            print(f"Error searching by object: {e}")
        
        return results
    
    def get_image_by_id(self, image_id: int) -> Optional[Dict]:
        """
        Retrieve single image metadata by ID.
        
        Args:
            image_id: Database image ID
        
        Returns:
            Image metadata dictionary or None
        """
        try:
            if self.db:
                return self.db.get_image_by_id(image_id)
        except Exception as e:
            print(f"Error fetching image by ID: {e}")
        return None
    
    def load_image_file(self, image_path: str) -> Optional[np.ndarray]:
        """
        Load image file from disk.
        Falls back to generating a placeholder image if file doesn't exist.
        
        Args:
            image_path: Full path to image file
        
        Returns:
            OpenCV image array or placeholder image
        """
        try:
            if not os.path.exists(image_path):
                print(f"Image not found: {image_path} - generating placeholder")
                return self._generate_placeholder_image(image_path)
            
            image = cv2.imread(image_path)
            if image is None:
                print(f"Failed to load image: {image_path} - generating placeholder")
                return self._generate_placeholder_image(image_path)
            
            return image
        except Exception as e:
            print(f"Error loading image: {e}")
            return self._generate_placeholder_image(image_path)
    
    def _generate_placeholder_image(self, image_name: str, width: int = 150, height: int = 150) -> np.ndarray:
        """
        Generate a placeholder image for testing.
        
        Args:
            image_name: Name of the image (used for label)
            width: Image width
            height: Image height
        
        Returns:
            Generated placeholder image
        """
        import hashlib
        
        # Generate a color based on image name hash
        hash_obj = hashlib.md5(image_name.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        
        b = (hash_int >> 16) & 255
        g = (hash_int >> 8) & 255
        r = hash_int & 255
        
        # Create placeholder image
        placeholder = np.full((height, width, 3), (b, g, r), dtype=np.uint8)
        
        # Add text label
        text = os.path.basename(image_name)[:20]
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.4
        thickness = 1
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = (width - text_size[0]) // 2
        text_y = (height + text_size[1]) // 2
        
        cv2.putText(placeholder, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)
        
        return placeholder


class InteractiveImageGallery:
    """
    Display and manage image gallery with hand gesture control.
    Integrates RAG retrieval with hand tracking for interactive browsing.
    """
    
    def __init__(self, width: int = 1280, height: int = 720):
        """
        Initialize interactive gallery.
        
        Args:
            width: Display width in pixels
            height: Display height in pixels
        """
        self.width = width
        self.height = height
        self.rag_retriever = RAGImageRetriever()
        self.gallery_images: List[Dict] = []
        self.selected_image = None
        self.pinch_state = False
        
        # Hand tracking
        import mediapipe as mp
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        )
        
        self.mp_draw = mp.solutions.drawing_utils
    
    def search_and_load_gallery(self, query: str, limit: int = 5) -> bool:
        """
        Search database and load images into gallery.
        
        Args:
            query: Search query string
            limit: Number of images to load
        
        Returns:
            True if images loaded successfully
        """
        print(f"Searching for: {query}")
        
        # Search database
        db_results = self.rag_retriever.search_images_by_query(query, limit=limit)
        
        if not db_results:
            print("No images found in database")
            return False
        
        # Load images and prepare for display
        self.gallery_images = []
        thumb_width, thumb_height = 150, 150
        
        for idx, result in enumerate(db_results):
            # Load image from path
            image_data = self.rag_retriever.load_image_file(result.get('path', ''))
            
            if image_data is not None:
                # Resize to thumbnail
                image_data = cv2.resize(image_data, (thumb_width, thumb_height))
                
                # Create gallery entry
                gallery_item = {
                    "image": image_data,
                    "name": result.get('name', f'Image_{idx}'),
                    "path": result.get('path', ''),
                    "id": result.get('id', -1),
                    "metadata": result,  # Store full metadata from DB
                    "x": 50 + (idx % 3) * 200,  # Position: 3 columns
                    "y": 150 + (idx // 3) * 200,  # Position: multiple rows
                    "w": thumb_width,
                    "h": thumb_height,
                    "grabbed": False
                }
                self.gallery_images.append(gallery_item)
                print(f"✓ Loaded: {gallery_item['name']}")
        
        print(f"Gallery loaded with {len(self.gallery_images)} images")
        return len(self.gallery_images) > 0
    
    def detect_hand_and_gesture(self, frame: np.ndarray) -> Tuple[Tuple[int, int], bool, str]:
        """
        Detect hand and classify gesture.
        
        Args:
            frame: Input video frame
        
        Returns:
            Tuple: (index_pos, is_pinching, gesture_name)
        """
        # Detect hand
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)
        
        index_pos = (0, 0)
        is_pinching = False
        gesture = "No Hand"
        
        if results.multi_hand_landmarks:
            for hand_lms, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                # Draw hand skeleton
                self.mp_draw.draw_landmarks(frame, hand_lms, self.mp_hands.HAND_CONNECTIONS)
                
                # Detect pinch
                is_pinching, index_pos, thumb_pos = detect_pinch_gesture(
                    hand_lms, self.width, self.height, threshold=50
                )
                
                # Classify gesture
                gesture = classify_gesture(hand_lms.landmark, handedness.classification[0].label)
        
        return index_pos, is_pinching, gesture
    
    def render_gallery(self, frame: np.ndarray, index_pos: Tuple[int, int], 
                       gesture: str, pinching: bool) -> np.ndarray:
        """
        Render gallery images on frame.
        
        Args:
            frame: Input frame to draw on
            index_pos: Current hand index position
            gesture: Current gesture name
            pinching: Whether pinching is detected
        
        Returns:
            Annotated frame
        """
        # Draw gallery images
        for img_item in self.gallery_images:
            # Resize and place image
            img_resized = cv2.resize(img_item['image'], (img_item['w'], img_item['h']))
            
            # Clip bounds
            y1 = max(0, img_item['y'])
            y2 = min(self.height, img_item['y'] + img_item['h'])
            x1 = max(0, img_item['x'])
            x2 = min(self.width, img_item['x'] + img_item['w'])
            
            if y2 > y1 and x2 > x1:
                frame[y1:y2, x1:x2] = img_resized[:y2-y1, :x2-x1]
            
            # Draw border (highlight if grabbed)
            color = COLORS['cyan'] if img_item['grabbed'] else (100, 100, 100)
            thickness = 3 if img_item['grabbed'] else 1
            draw_rectangle(frame, (img_item['x'], img_item['y']), 
                          (img_item['x'] + img_item['w'], img_item['y'] + img_item['h']), 
                          color, thickness)
            
            # Draw image name
            draw_text(frame, img_item['name'][:15], 
                     (img_item['x'], img_item['y'] - 5),
                     font_scale=0.4, color=COLORS['white'], thickness=1)
        
        # Draw hand cursor
        draw_filled_circle(frame, index_pos, radius=8, color=COLORS['green'])
        
        # Draw status bar
        status_text = f"Gesture: {gesture} | Pinching: {pinching}"
        draw_text(frame, status_text, (10, 30),
                   font_scale=0.7, color=COLORS['green'], thickness=2)
        
        # Draw instructions
        instructions = "Move hand to select | Pinch to grab | Release to drop"
        draw_text(frame, instructions, (10, self.height - 20),
                 font_scale=0.6, color=COLORS['white'], thickness=1)
        
        return frame
    
    def run_interactive_gallery(self, query: str = "home objects"):
        """
        Run interactive gallery with hand gesture control.
        
        Args:
            query: Initial search query
        """
        # Load images from database
        if not self.search_and_load_gallery(query):
            print("Could not load images. Exiting.")
            return
        
        # Initialize camera
        cap = init_camera()
        if not cap.isOpened():
            print("Cannot open camera")
            return
        
        # Initialize FPS counter
        fps_counter = FPSCounter()
        
        print("\n=== Interactive Gallery ===")
        print("✓ Camera opened")
        print("✓ Press ESC to exit")
        print("✓ Pinch to grab and drag images")
        
        while True:
            success, frame = cap.read()
            if not success:
                print("Failed to read frame")
                break
            
            frame = mirror_frame(frame)  # Mirror
            
            # Get frame dimensions
            h, w = frame.shape[:2]
            self.width = w
            self.height = h
            
            # Detect hand and gesture
            index_pos, is_pinching, gesture = self.detect_hand_and_gesture(frame)
            
            # Handle selection/movement/release
            if is_pinching and not self.pinch_state:
                # Start pinch
                self.selected_image = select_image(index_pos, self.gallery_images)
                self.pinch_state = True
            elif is_pinching and self.selected_image:
                # Continue pinching - move image
                move_selected_image(index_pos, self.selected_image)
            elif not is_pinching and self.pinch_state:
                # Release
                self.selected_image = release_image(self.selected_image)
                self.pinch_state = False
            
            # Render gallery
            frame = self.render_gallery(frame, index_pos, gesture, is_pinching)
            
            # Calculate and display FPS
            fps = fps_counter.update()
            draw_text(frame, f"FPS: {fps:.1f}", (self.width - 150, 30),
                     font_scale=0.7, color=COLORS['green'], thickness=2)
            
            # Display
            if display_frame("Interactive Gallery - Hand Gesture Control", frame):
                break
        
        # Cleanup
        close_camera_and_windows(cap)
        self.hands.close()
        print("Gallery closed")


def demo_rag_image_retrieval():
    """Demo: Retrieve images from database and display"""
    print("=== RAG Image Retrieval Demo ===\n")
    
    retriever = RAGImageRetriever(use_gemini=True)
    
    # Search for images
    query = "living room furniture"
    print(f"Searching for: {query}")
    results = retriever.search_images_by_query(query, limit=5)
    
    if results:
        print(f"\nFound {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.get('name', 'Unknown')} (ID: {result.get('id', 'N/A')})")
            print(f"   Path: {result.get('path', 'N/A')}")
    else:
        print("No results found")


def demo_interactive_gallery():
    """Demo: Run interactive gallery with hand gestures"""
    print("=== Interactive Gallery Demo ===\n")
    
    gallery = InteractiveImageGallery(width=1280, height=720)
    gallery.run_interactive_gallery(query="home objects")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG Client - Image Retrieval & Display")
    parser.add_argument("--mode", type=str, default="gallery", 
                       choices=["retrieve", "gallery"],
                       help="Mode: retrieve (search only) or gallery (interactive)")
    parser.add_argument("--query", type=str, default="home objects",
                       help="Search query")
    
    args = parser.parse_args()
    
    if args.mode == "retrieve":
        demo_rag_image_retrieval()
    else:
        demo_interactive_gallery()
