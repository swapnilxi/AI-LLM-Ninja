import cv2
import mediapipe as mp
import math
import numpy as np

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# Utility: count raised fingers (simple heuristic for one hand)
def fingers_up(landmarks, handedness):
    # Indices: Thumb(4), Index(8), Middle(12), Ring(16), Pinky(20)
    tips = [4, 8, 12, 16, 20]
    # For non-thumb fingers, compare tip y to PIP y (lower y = up in image coords)
    pip = [None, 6, 10, 14, 18]
    fingers = [0,0,0,0,0]
    # Thumb: compare x depending on left/right hand (horizontal check)
    if handedness == "Right":
        fingers[0] = 1 if landmarks[4].x < landmarks[3].x else 0
    else:
        fingers[0] = 1 if landmarks[4].x > landmarks[3].x else 0
    # Other 4 fingers
    for i, tip_idx in enumerate(tips[1:], start=1):
        fingers[i] = 1 if landmarks[tip_idx].y < landmarks[pip[i]].y else 0
    return sum(fingers), fingers

# Simple gesture rules:
# - Fist: 0
# - One: 1 (index up)
# - Peace/V: 2 (index+middle)
# - Three/Four/Five by count
# - Thumbs up: thumb up, others down + thumb above wrist vertically
def classify_gesture(landmarks, handedness):
    count, mask = fingers_up(landmarks, handedness)
    # Thumbs up check (tip higher than wrist and other fingers down)
    wrist = landmarks[0]
    thumb_tip = landmarks[4]
    others_down = sum(mask[1:]) == 0
    thumbs_up = (thumb_tip.y < wrist.y) and (mask[0] == 1) and others_down
    if thumbs_up:
        return "Thumbs Up"
    return {
        0: "Fist",
        1: "One",
        2: "Peace",
        3: "Three",
        4: "Four",
        5: "Five"
    }.get(count, f"{count} Fingers")


def detect_pinch_gesture(hand_landmarks, frame_width, frame_height, threshold=50):
    """
    Detect pinch gesture by measuring distance between thumb and index finger.
    
    Args:
        hand_landmarks: MediaPipe hand landmarks
        frame_width: Width of the frame
        frame_height: Height of the frame
        threshold: Distance threshold for pinch detection (default: 50 pixels)
        
    Returns:
        tuple: (is_pinching, index_finger_pos, thumb_pos)
    """
    # Get thumb (4) and index finger (8) positions
    index_finger = hand_landmarks.landmark[8]
    thumb_finger = hand_landmarks.landmark[4]
    
    ix = int(index_finger.x * frame_width)
    iy = int(index_finger.y * frame_height)
    tx = int(thumb_finger.x * frame_width)
    ty = int(thumb_finger.y * frame_height)
    
    # Calculate distance between thumb and index
    dist = np.hypot(ix - tx, iy - ty)
    is_pinching = dist < threshold
    
    return is_pinching, (ix, iy), (tx, ty)


def is_inside_box(px, py, x, y, w, h):
    """
    Check if a point is inside a bounding box.
    
    Args:
        px, py: Point coordinates
        x, y: Box top-left corner
        w, h: Box width and height
        
    Returns:
        bool: True if point is inside box
    """
    return (x <= px <= x + w) and (y <= py <= y + h)


def select_image(pointer, images):
    """
    Select an image that contains the pointer position.
    
    Args:
        pointer: (x, y) tuple of pointer position
        images: List of image dictionaries with 'x', 'y', 'w', 'h' keys
        
    Returns:
        dict: Selected image dict, or None if no image at pointer
    """
    for img in images:
        if is_inside_box(pointer[0], pointer[1], img["x"], img["y"], img["w"], img["h"]):
            img["grabbed"] = True
            return img
    return None


def move_selected_image(pointer, selected_image):
    """
    Move the selected image to follow the pointer (hand/mouse).
    
    Args:
        pointer: (x, y) tuple of pointer position
        selected_image: Image dictionary to move
    """
    if selected_image is not None:
        selected_image["x"] = pointer[0] - selected_image["w"] // 2
        selected_image["y"] = pointer[1] - selected_image["h"] // 2


def release_image(selected_image):
    """
    Release the currently selected image.
    
    Args:
        selected_image: Image dictionary to release
        
    Returns:
        None
    """
    if selected_image is not None:
        selected_image["grabbed"] = False
    return None


def draw_soft_glow(frame, pos, radius=40, color=(0, 255, 255)):
    """
    Draw a soft glow effect at the given position.
    
    Args:
        frame: Input frame to draw on
        pos: (x, y) center position
        radius: Maximum radius of glow
        color: BGR color tuple
        
    Returns:
        frame: Modified frame with glow
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


# ============== EXAMPLE USAGE ==============
if __name__ == "__main__":
    cap = cv2.VideoCapture(0)
    with mp_hands.Hands(
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    ) as hands:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)  # mirror
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = hands.process(rgb)

            gesture_text = "No Hand"
            if res.multi_hand_landmarks:
                for hand_lms, handed in zip(res.multi_hand_landmarks, res.multi_handedness):
                    mp_drawing.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)

                    # Detect pinch gesture
                    h, w, _ = frame.shape
                    is_pinch, idx_pos, thumb_pos = detect_pinch_gesture(hand_lms, w, h)
                    
                    # Draw soft glow on index finger
                    frame = draw_soft_glow(frame, idx_pos, radius=40, color=(0, 255, 255))
                    
                    # Get gesture classification
                    gesture_text = classify_gesture(hand_lms.landmark, handed.classification[0].label)
                    
                    cv2.putText(frame, f"Gesture: {gesture_text}", (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    if is_pinch:
                        cv2.putText(frame, "PINCHING", (20, 80),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            cv2.imshow("Hand Gesture", frame)
            if cv2.waitKey(1) & 0xFF == 27:  # ESC
                break
            
    cap.release()
    cv2.destroyAllWindows()
