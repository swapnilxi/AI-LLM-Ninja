import cv2
import mediapipe as mp
import numpy as np 
import time 

# MediaPipe Hand Detection Setup
mpHands = mp.solutions.hands
mpDraw = mp.solutions.drawing_utils


def detect_hand_landmarks(frame, hands):
    """
    Detect hand landmarks in a frame using MediaPipe.
    
    Args:
        frame: Input video frame (BGR image)
        hands: MediaPipe Hands object
        
    Returns:
        tuple: (frame with drawn landmarks, multi_hand_landmarks, multi_handedness)
    """
    imgRGB = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(imgRGB)
    
    if results.multi_hand_landmarks:
        for handLms in results.multi_hand_landmarks:
            # Draw hand landmarks and connections
            mpDraw.draw_landmarks(frame, handLms, mp.solutions.hands.HAND_CONNECTIONS)
    
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
    landmark = landmarks.landmark[finger_idx]
    x = int(landmark.x * frame_width)
    y = int(landmark.y * frame_height)
    return (x, y)


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
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)
    pinch = False
    index_pos = (0, 0)

    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            # Draw hand landmarks
            mpDraw.draw_landmarks(frame, hand_landmarks, mp.solutions.hands.HAND_CONNECTIONS)

            # Get thumb (4) and index finger (8) positions
            index_finger = hand_landmarks.landmark[8]
            thumb_finger = hand_landmarks.landmark[4]

            ix, iy = int(index_finger.x * width), int(index_finger.y * height)
            tx, ty = int(thumb_finger.x * width), int(thumb_finger.y * height)
            index_pos = (ix, iy)

            # Detect pinch gesture (close distance between thumb and index)
            dist = np.hypot(ix - tx, iy - ty)
            if dist < 50:  # Pinch threshold
                pinch = True

    return index_pos, pinch, frame


# ============== EXAMPLE USAGE ==============
if __name__ == "__main__":
    cap = cv2.VideoCapture(0)
    hands = mpHands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    )
    
    ptime = 0
    
    while True:
        success, img = cap.read()
        if not success:
            break
            
        frame, multi_hand_landmarks, multi_handedness = detect_hand_landmarks(img, hands)
        
        # Print hand landmarks for debugging
        if multi_hand_landmarks:
            for handLms in multi_hand_landmarks:
                for id, lm in enumerate(handLms.landmark):
                    h, w, c = img.shape
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    print(f"Landmark {id}: ({cx}, {cy})")
                    
                    # Highlight thumb (id 4)
                    if id == 4:
                        cv2.circle(frame, (cx, cy), 15, (255, 0, 255), cv2.FILLED)
        
        # Calculate and display FPS
        ctime = time.time()
        fps = 1 / (ctime - ptime) if ptime != 0 else 0
        ptime = ctime
        
        cv2.putText(frame, str(int(fps)), (10, 70), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 255), 3)
        
        cv2.imshow("Hand Recognition", frame)
        
        if cv2.waitKey(1) & 0xFF == 27:  # ESC to exit
            break
    
    cap.release()
    hands.close()
    cv2.destroyAllWindows() 