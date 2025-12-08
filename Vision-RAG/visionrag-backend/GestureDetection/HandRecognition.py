import cv2
import numpy as np 
import time
from gesture_utils import (
    init_mediapipe_hands,
    bgr_to_rgb,
    normalize_to_pixel,
    euclidean_distance,
    init_camera,
    display_frame,
    close_camera_and_windows,
    FPSCounter,
    draw_filled_circle,
    COLORS
)


def detect_hand_landmarks(frame, hands):
    """
    Detect hand landmarks in a frame using MediaPipe.
    
    Args:
        frame: Input video frame (BGR image)
        hands: MediaPipe Hands object
        
    Returns:
        tuple: (frame with drawn landmarks, multi_hand_landmarks, multi_handedness)
    """
    rgb = bgr_to_rgb(frame)
    results = hands.process(rgb)
    
    if results.multi_hand_landmarks:
        import mediapipe as mp
        mp_drawing = mp.solutions.drawing_utils
        mp_hands = mp.solutions.hands
        for handLms in results.multi_hand_landmarks:
            # Draw hand landmarks and connections
            mp_drawing.draw_landmarks(frame, handLms, mp_hands.HAND_CONNECTIONS)
    
    return frame, results.multi_hand_landmarks, results.multi_handedness


def get_finger_position(landmarks, frame_width, frame_height, finger_idx):
    """
    Get the (x, y) position of a specific finger landmark.
    
    Args:
        landmarks: Hand landmarks from MediaPipe
        frame_width: Width of the video frame
        frame_height: Height of the video frame
        finger_idx: Index of the finger (0-20 for hand landmarks)
        
    Returns:
        tuple: (x, y) pixel coordinates
    """
    return normalize_to_pixel(landmarks.landmark[finger_idx].x, 
                             landmarks.landmark[finger_idx].y, 
                             frame_width, frame_height)


def detect_hand_gesture(frame, hands, width, height):
    """
    Detect hand position and pinch gesture.
    
    Args:
        frame: Input video frame (BGR image)
        hands: MediaPipe Hands object
        width: Frame width
        height: Frame height
        
    Returns:
        tuple: (index_finger_pos, is_pinching, frame_with_landmarks)
    """
    rgb = bgr_to_rgb(frame)
    result = hands.process(rgb)
    pinch = False
    index_pos = (0, 0)

    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            # Draw hand landmarks
            import mediapipe as mp
            mp_drawing = mp.solutions.drawing_utils
            mp_hands = mp.solutions.hands
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            # Get thumb (4) and index finger (8) positions
            index_finger = hand_landmarks.landmark[8]
            thumb_finger = hand_landmarks.landmark[4]

            ix, iy = normalize_to_pixel(index_finger.x, index_finger.y, width, height)
            tx, ty = normalize_to_pixel(thumb_finger.x, thumb_finger.y, width, height)
            index_pos = (ix, iy)

            # Detect pinch gesture (close distance between thumb and index)
            dist = euclidean_distance(ix, iy, tx, ty)
            if dist < 50:  # Pinch threshold
                pinch = True

    return index_pos, pinch, frame


# ============== EXAMPLE USAGE ==============
if __name__ == "__main__":
    cap = init_camera()
    hands, mp_drawing = init_mediapipe_hands(static_image_mode=False, max_num_hands=2)
    fps_counter = FPSCounter()
    
    while True:
        success, img = cap.read()
        if not success:
            break
            
        frame, multi_hand_landmarks, multi_handedness = detect_hand_landmarks(img, hands)
        
        # Print hand landmarks for debugging
        h, w, c = img.shape
        if multi_hand_landmarks:
            for handLms in multi_hand_landmarks:
                for id, lm in enumerate(handLms.landmark):
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    print(f"Landmark {id}: ({cx}, {cy})")
                    
                    # Highlight thumb (id 4)
                    if id == 4:
                        frame = draw_filled_circle(frame, (cx, cy), 15, COLORS['magenta'])
        
        # Update and display FPS
        fps = fps_counter.update()
        cv2.putText(frame, str(int(fps)), (10, 70), cv2.FONT_HERSHEY_PLAIN, 3, COLORS['magenta'], 3)
        
        # Display frame and check for ESC
        if display_frame("Hand Recognition", frame):
            break
    
    close_camera_and_windows(cap)
    hands.close()
 