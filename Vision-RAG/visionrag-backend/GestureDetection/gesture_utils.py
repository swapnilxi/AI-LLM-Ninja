"""
Gesture Detection Utilities Module
Contains reusable functions for hand gesture recognition, drawing, and coordinate conversions.
Used by HandGestures.py, HandRecognition.py, and rag_client.py to avoid code duplication.
"""

import cv2
import mediapipe as mp
import numpy as np
from typing import Tuple, List, Optional, Any


# ============== MEDIAPIPE INITIALIZATION ==============

def init_mediapipe_hands(
    max_num_hands: int = 1,
    model_complexity: int = 1,
    min_detection_confidence: float = 0.6,
    min_tracking_confidence: float = 0.6,
    static_image_mode: bool = False
) -> Tuple[mp.solutions.hands.Hands, Any]:
    """
    Initialize MediaPipe Hands detector and drawing utilities.
    
    Args:
        max_num_hands: Maximum number of hands to detect
        model_complexity: Complexity of the hand detection model (0 or 1)
        min_detection_confidence: Minimum detection confidence threshold
        min_tracking_confidence: Minimum tracking confidence threshold
        static_image_mode: Whether to run on static images or video
    
    Returns:
        tuple: (hands object, drawing utils object)
    """
    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    
    hands = mp_hands.Hands(
        static_image_mode=static_image_mode,
        max_num_hands=max_num_hands,
        model_complexity=model_complexity,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence
    )
    
    return hands, mp_draw


# ============== COORDINATE CONVERSION ==============

def bgr_to_rgb(frame) -> np.ndarray:
    """
    Convert BGR frame to RGB.
    Used for MediaPipe processing (which expects RGB input).
    
    Args:
        frame: BGR frame from OpenCV
    
    Returns:
        RGB frame
    """
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def normalize_to_pixel(
    normalized_x: float,
    normalized_y: float,
    frame_width: int,
    frame_height: int
) -> Tuple[int, int]:
    """
    Convert normalized coordinates (0-1) to pixel coordinates.
    MediaPipe landmarks are normalized; convert them to pixel coords.
    
    Args:
        normalized_x: X coordinate in normalized space (0-1)
        normalized_y: Y coordinate in normalized space (0-1)
        frame_width: Width of the frame in pixels
        frame_height: Height of the frame in pixels
    
    Returns:
        tuple: (x_pixel, y_pixel) in integer pixel coordinates
    """
    x_pixel = int(normalized_x * frame_width)
    y_pixel = int(normalized_y * frame_height)
    return (x_pixel, y_pixel)


def clamp_to_bounds(
    x: int,
    y: int,
    width: int,
    height: int
) -> Tuple[int, int]:
    """
    Clamp x, y coordinates to frame bounds.
    
    Args:
        x, y: Coordinates to clamp
        width, height: Frame dimensions
    
    Returns:
        tuple: (clamped_x, clamped_y)
    """
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    return (x, y)


# ============== DISTANCE AND GEOMETRY ==============

def euclidean_distance(x1: int, y1: int, x2: int, y2: int) -> float:
    """
    Calculate Euclidean distance between two points.
    Used for pinch gesture detection and collision checking.
    
    Args:
        x1, y1: First point coordinates
        x2, y2: Second point coordinates
    
    Returns:
        float: Distance between the two points
    """
    return np.hypot(x2 - x1, y2 - y1)


def point_in_box(px: int, py: int, x: int, y: int, w: int, h: int) -> bool:
    """
    Check if a point (px, py) is inside a bounding box.
    
    Args:
        px, py: Point coordinates
        x, y: Box top-left corner
        w, h: Box width and height
    
    Returns:
        bool: True if point is inside box
    """
    return (x <= px <= x + w) and (y <= py <= y + h)


def distance_between_landmarks(
    landmark1: Any,
    landmark2: Any,
    frame_width: int,
    frame_height: int
) -> float:
    """
    Calculate pixel distance between two MediaPipe landmarks.
    
    Args:
        landmark1, landmark2: MediaPipe landmark objects with x, y, z attributes
        frame_width, frame_height: Frame dimensions for pixel conversion
    
    Returns:
        float: Distance in pixels
    """
    x1, y1 = normalize_to_pixel(landmark1.x, landmark1.y, frame_width, frame_height)
    x2, y2 = normalize_to_pixel(landmark2.x, landmark2.y, frame_width, frame_height)
    return euclidean_distance(x1, y1, x2, y2)


# ============== DRAWING UTILITIES ==============

def draw_filled_circle(
    frame: np.ndarray,
    center: Tuple[int, int],
    radius: int = 8,
    color: Tuple[int, int, int] = (0, 255, 0)
) -> np.ndarray:
    """
    Draw a filled circle on the frame.
    
    Args:
        frame: Input frame to draw on
        center: (x, y) center position
        radius: Circle radius in pixels
        color: BGR color tuple
    
    Returns:
        Modified frame
    """
    cv2.circle(frame, center, radius, color, -1)
    return frame


def draw_rectangle(
    frame: np.ndarray,
    top_left: Tuple[int, int],
    bottom_right: Tuple[int, int],
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2
) -> np.ndarray:
    """
    Draw a rectangle on the frame.
    
    Args:
        frame: Input frame to draw on
        top_left: (x, y) of top-left corner
        bottom_right: (x, y) of bottom-right corner
        color: BGR color tuple
        thickness: Line thickness (-1 for filled)
    
    Returns:
        Modified frame
    """
    cv2.rectangle(frame, top_left, bottom_right, color, thickness)
    return frame


def draw_text(
    frame: np.ndarray,
    text: str,
    position: Tuple[int, int],
    font_scale: float = 1.0,
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
    font: int = cv2.FONT_HERSHEY_SIMPLEX
) -> np.ndarray:
    """
    Draw text on the frame.
    
    Args:
        frame: Input frame to draw on
        text: Text string to draw
        position: (x, y) position for text
        font_scale: Font size scale
        color: BGR color tuple
        thickness: Text thickness
        font: OpenCV font type
    
    Returns:
        Modified frame
    """
    cv2.putText(frame, text, position, font, font_scale, color, thickness)
    return frame


def draw_soft_glow(
    frame: np.ndarray,
    pos: Tuple[int, int],
    radius: int = 40,
    color: Tuple[int, int, int] = (0, 255, 255)
) -> np.ndarray:
    """
    Draw a soft glow effect at the given position.
    Creates concentric circles with decreasing opacity for a glow effect.
    
    Args:
        frame: Input frame to draw on
        pos: (x, y) center position
        radius: Maximum radius of glow
        color: BGR color tuple
    
    Returns:
        Modified frame with glow
    """
    overlay = frame.copy()
    
    # Draw concentric circles with decreasing alpha
    for r, alpha in [(radius, 0.1), (int(radius * 0.625), 0.2), (int(radius * 0.3), 0.3)]:
        cv2.circle(overlay, pos, r, color, -1)
    
    # Blend overlay with original
    frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
    
    # Add small bright core
    cv2.circle(frame, pos, 6, (255, 255, 255), -1)
    
    return frame


def draw_hand_landmarks(
    frame: np.ndarray,
    hand_landmarks,
    mp_draw,
    mp_hands
) -> np.ndarray:
    """
    Draw hand landmarks and connections on the frame.
    
    Args:
        frame: Input frame to draw on
        hand_landmarks: MediaPipe hand landmarks object
        mp_draw: MediaPipe drawing utilities
        mp_hands: MediaPipe hands solution
    
    Returns:
        Modified frame
    """
    mp_draw.draw_landmarks(
        frame,
        hand_landmarks,
        mp_hands.HAND_CONNECTIONS
    )
    return frame


# ============== VIDEO PROCESSING ==============

def init_camera(camera_id: int = 0) -> cv2.VideoCapture:
    """
    Initialize camera capture.
    
    Args:
        camera_id: Camera device ID (0 for default)
    
    Returns:
        cv2.VideoCapture object
    """
    return cv2.VideoCapture(camera_id)


def mirror_frame(frame: np.ndarray) -> np.ndarray:
    """
    Mirror the frame horizontally (flip left-right).
    Useful for webcam feeds to match user's perspective.
    
    Args:
        frame: Input frame
    
    Returns:
        Mirrored frame
    """
    return cv2.flip(frame, 1)


def display_frame(
    window_name: str = "Frame",
    frame: np.ndarray = None,
    wait_ms: int = 1
) -> bool:
    """
    Display frame in a window.
    
    Args:
        window_name: Name of the window
        frame: Frame to display
        wait_ms: Wait time in milliseconds (1 = 1ms, 27 = ESC key)
    
    Returns:
        bool: True if ESC (key 27) was pressed, False otherwise
    """
    cv2.imshow(window_name, frame)
    key = cv2.waitKey(wait_ms)
    return (key & 0xFF) == 27  # ESC key


def close_camera_and_windows(cap: cv2.VideoCapture) -> None:
    """
    Close camera capture and destroy all windows.
    
    Args:
        cap: cv2.VideoCapture object to release
    """
    cap.release()
    cv2.destroyAllWindows()


# ============== FPS CALCULATION ==============

class FPSCounter:
    """
    Helper class to calculate and track FPS in video loops.
    """
    
    def __init__(self):
        """Initialize FPS counter"""
        self.prev_time = 0
        self.current_fps = 0
    
    def update(self) -> float:
        """
        Update and return current FPS.
        Call this once per frame.
        
        Returns:
            float: Current FPS (frames per second)
        """
        import time
        current_time = time.time()
        
        if self.prev_time != 0:
            self.current_fps = 1 / (current_time - self.prev_time)
        
        self.prev_time = current_time
        return self.current_fps
    
    def get_fps(self) -> float:
        """
        Get the current FPS value without updating.
        
        Returns:
            float: Last calculated FPS
        """
        return self.current_fps


# ============== LANDMARK UTILITIES ==============

def get_landmark_position(
    landmarks,
    landmark_idx: int,
    frame_width: int,
    frame_height: int
) -> Tuple[int, int]:
    """
    Get pixel position of a specific landmark.
    
    Args:
        landmarks: MediaPipe landmarks object
        landmark_idx: Index of the landmark (0-20 for hands)
        frame_width, frame_height: Frame dimensions
    
    Returns:
        tuple: (x, y) in pixel coordinates
    """
    landmark = landmarks.landmark[landmark_idx]
    return normalize_to_pixel(landmark.x, landmark.y, frame_width, frame_height)


def get_hand_center(
    landmarks,
    frame_width: int,
    frame_height: int
) -> Tuple[int, int]:
    """
    Calculate the center point of the hand (average of all landmarks).
    
    Args:
        landmarks: MediaPipe landmarks object
        frame_width, frame_height: Frame dimensions
    
    Returns:
        tuple: (x, y) center position in pixels
    """
    x_coords = [l.x for l in landmarks.landmark]
    y_coords = [l.y for l in landmarks.landmark]
    
    avg_x = sum(x_coords) / len(x_coords)
    avg_y = sum(y_coords) / len(y_coords)
    
    return normalize_to_pixel(avg_x, avg_y, frame_width, frame_height)


# ============== WINDOW MANAGEMENT ==============

def create_window(window_name: str, width: int = None, height: int = None) -> None:
    """
    Create a named window with optional size.
    
    Args:
        window_name: Name of the window
        width, height: Optional window dimensions (if None, auto-sized)
    """
    cv2.namedWindow(window_name)
    if width and height:
        cv2.resizeWindow(window_name, width, height)


def destroy_window(window_name: str) -> None:
    """
    Destroy a specific window.
    
    Args:
        window_name: Name of the window to destroy
    """
    cv2.destroyWindow(window_name)


# ============== CONSTANTS ==============

# Landmark indices for quick reference
LANDMARK_INDICES = {
    'wrist': 0,
    'thumb_tip': 4,
    'index_tip': 8,
    'middle_tip': 12,
    'ring_tip': 16,
    'pinky_tip': 20,
    'thumb_pip': 3,
    'index_pip': 6,
    'middle_pip': 10,
    'ring_pip': 14,
    'pinky_pip': 18,
}

# Default pinch detection threshold in pixels
DEFAULT_PINCH_THRESHOLD = 50

# Gesture names
GESTURE_NAMES = {
    0: "Fist",
    1: "One",
    2: "Peace",
    3: "Three",
    4: "Four",
    5: "Five",
    "thumbs_up": "Thumbs Up",
    "pinch": "Pinch"
}

# Color definitions (BGR format)
COLORS = {
    'green': (0, 255, 0),
    'red': (0, 0, 255),
    'blue': (255, 0, 0),
    'yellow': (0, 255, 255),
    'cyan': (255, 255, 0),
    'magenta': (255, 0, 255),
    'white': (255, 255, 255),
    'black': (0, 0, 0),
}
