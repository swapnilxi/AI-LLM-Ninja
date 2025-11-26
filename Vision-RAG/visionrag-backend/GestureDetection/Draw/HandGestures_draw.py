import cv2
import mediapipe as mp
from collections import deque
import math

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# --- Gesture utilities (merged from HandGestures.py) ---
def fingers_up(landmarks, handedness):
    # Indices: Thumb(4), Index(8), Middle(12), Ring(16), Pinky(20)
    tips = [4, 8, 12, 16, 20]
    # For non-thumb fingers, compare tip y to PIP y (lower y = up in image coords)
    pip = [None, 6, 10, 14, 18]
    fingers = [0, 0, 0, 0, 0]
    # Thumb: compare x depending on left/right hand (horizontal check)
    try:
        if handedness == "Right":
            fingers[0] = 1 if landmarks[4].x < landmarks[3].x else 0
        else:
            fingers[0] = 1 if landmarks[4].x > landmarks[3].x else 0
    except Exception:
        # Fallback if handedness not provided as expected
        fingers[0] = 0
    # Other 4 fingers
    for i, tip_idx in enumerate(tips[1:], start=1):
        try:
            fingers[i] = 1 if landmarks[tip_idx].y < landmarks[pip[i]].y else 0
        except Exception:
            fingers[i] = 0
    return sum(fingers), fingers

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

canvas = None
drawing = False
prev_point = None
undo_stack = deque(maxlen=10)
redo_stack = deque(maxlen=10)

# --- Button layout (centered at top) ---
def get_button_positions(w):
    btn_w, btn_h, gap = 120, 50, 20
    total_w = 4 * btn_w + 3 * gap
    start_x = (w - total_w) // 2
    y1, y2 = 40, 90
    names = ["Draw", "Clear", "Undo", "Redo"]
    return {name: (start_x + i * (btn_w + gap), y1, start_x + i * (btn_w + gap) + btn_w, y2)
            for i, name in enumerate(names)}

def draw_buttons(frame, buttons, drawing):
    for name, (x1, y1, x2, y2) in buttons.items():
        if name == "Draw" and drawing:
            color = (0, 200, 0)
        elif name == "Clear":
            color = (60, 60, 255)
        elif name == "Undo":
            color = (255, 140, 0)
        elif name == "Redo":
            color = (0, 165, 255)
        else:
            color = (80, 80, 80)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
        cv2.putText(frame, name, (x1 + 20, y2 - 15), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 255), 2)

def check_button_press(x, y, buttons):
    for name, (x1, y1, x2, y2) in buttons.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name
    return None

def distance(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

PINCH_THRESHOLD = 40   # pixel distance threshold for pinch toggle
pinch_active = False   # prevent rapid toggling

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
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        buttons = get_button_positions(w)
        if canvas is None:
            canvas = frame.copy() * 0

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = hands.process(rgb)

        # default
        gesture_text = "No Hand"
        if res.multi_hand_landmarks:
            # iterate with handedness so we can pass left/right info to classifier
            for hand_lms, handed in zip(res.multi_hand_landmarks, getattr(res, 'multi_handedness', [])):
                mp_drawing.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)

                # compute handedness label safely
                try:
                    handedness_label = handed.classification[0].label
                except Exception:
                    handedness_label = None

                # --- gesture classification ---
                try:
                    gesture_text = classify_gesture(hand_lms.landmark, handedness_label)
                except Exception:
                    gesture_text = "Unknown"

                # Index & thumb tip coordinates
                idx_tip = hand_lms.landmark[8]
                thumb_tip = hand_lms.landmark[4]
                cx, cy = int(idx_tip.x * w), int(idx_tip.y * h)
                tx, ty = int(thumb_tip.x * w), int(thumb_tip.y * h)

                # --- Glow Effect ---
                overlay = frame.copy()
                for radius, alpha in [(40, 0.1), (25, 0.2), (12, 0.3)]:
                    cv2.circle(overlay, (cx, cy), radius, (0, 255, 255), -1)
                frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
                cv2.circle(frame, (cx, cy), 6, (255, 255, 255), -1)

                # --- Pinch detection ---
                dist = distance((cx, cy), (tx, ty))
                if dist < PINCH_THRESHOLD and not pinch_active:
                    drawing = not drawing
                    pinch_active = True
                elif dist >= PINCH_THRESHOLD:
                    pinch_active = False

                # --- Button press detection ---
                pressed = check_button_press(cx, cy, buttons)
                if pressed == "Draw":
                    drawing = not drawing
                elif pressed == "Clear":
                    undo_stack.append(canvas.copy())
                    canvas[:] = 0
                    redo_stack.clear()
                elif pressed == "Undo" and undo_stack:
                    redo_stack.append(canvas.copy())
                    canvas = undo_stack.pop()
                elif pressed == "Redo" and redo_stack:
                    undo_stack.append(canvas.copy())
                    canvas = redo_stack.pop()

                # --- Drawing logic ---
                if drawing and pressed is None:
                    if prev_point:
                        cv2.line(canvas, prev_point, (cx, cy), (0, 255, 255), 8)
                    prev_point = (cx, cy)
                else:
                    prev_point = None

        # Combine and show buttons
        frame = cv2.addWeighted(frame, 0.7, canvas, 1, 0)
        draw_buttons(frame, buttons, drawing)
        # show detected gesture
        cv2.putText(frame, gesture_text, (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        cv2.putText(frame, "'Pinch'=Draw Toggle  |  'd'=Draw  'c'=Clear  'z'=Undo  'y'=Redo  'ESC'=Exit",
                    (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

        cv2.imshow("Hand Drawing (Glow + Buttons + Pinch Toggle)", frame)

        # --- Keyboard Controls ---
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            break
        elif key == ord('d'):
            drawing = not drawing
        elif key == ord('c'):
            undo_stack.append(canvas.copy())
            canvas[:] = 0
            redo_stack.clear()
        elif key == ord('z') and undo_stack:
            redo_stack.append(canvas.copy())
            canvas = undo_stack.pop()
        elif key == ord('y') and redo_stack:
            undo_stack.append(canvas.copy())
            canvas = redo_stack.pop()

cap.release()
cv2.destroyAllWindows()
