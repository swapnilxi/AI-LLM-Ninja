import cv2
import mediapipe as mp
import math

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

                # --- SOFT GLOW ON INDEX FINGER TIP ---
                h, w, _ = frame.shape
                idx_tip = hand_lms.landmark[8]  # Index finger tip
                cx, cy = int(idx_tip.x * w), int(idx_tip.y * h)

                overlay = frame.copy()
                # Draw concentric circles with decreasing alpha
                for radius, alpha in [(40, 0.1), (25, 0.2), (12, 0.3)]:
                    cv2.circle(overlay, (cx, cy), radius, (0, 255, 255), -1)  # yellow glow

                # Blend overlay with original
                frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)

                # --- OPTIONAL: add small bright core ---
                cv2.circle(frame, (cx, cy), 6, (255, 255, 255), -1)

                # Label gesture if you had gesture_text earlier
                cv2.putText(frame, "Glow Demo", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                cv2.putText(frame, gesture_text, (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow("Hand Gesture", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            break
        
cap.release()
cv2.destroyAllWindows()
