import cv2
import mediapipe as mp
from collections import deque
import math
import time

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

canvas = None
draw_enabled = False     # Toggle mode
drawing = False          # Actively drawing (while pinched)
prev_point = None
undo_stack = deque(maxlen=10)
redo_stack = deque(maxlen=10)

current_color = (0, 255, 255)
PINCH_THRESHOLD = 40
COLOR_CHANGE_THRESHOLD = 40
last_color_change_time = 0
COLOR_COOLDOWN = 1.0

# Predefined palette for natural cycling
palette = [(255, 0, 0), (0, 255, 0), (0, 255, 255), (255, 0, 255), (255, 165, 0), (255, 255, 255)]
color_index = 0

def get_button_positions(w):
    btn_w, btn_h, gap = 120, 50, 20
    total_w = 4 * btn_w + 3 * gap
    start_x = (w - total_w) // 2
    y1, y2 = 40, 90
    names = ["Draw", "Clear", "Undo", "Redo"]
    return {name: (start_x + i * (btn_w + gap), y1, start_x + i * (btn_w + gap) + btn_w, y2)
            for i, name in enumerate(names)}

def draw_buttons(frame, buttons, draw_enabled):
    for name, (x1, y1, x2, y2) in buttons.items():
        if name == "Draw" and draw_enabled:
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

        if res.multi_hand_landmarks:
            for hand_lms in res.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)

                idx_tip = hand_lms.landmark[8]
                mid_tip = hand_lms.landmark[12]
                thumb_tip = hand_lms.landmark[4]

                cx, cy = int(idx_tip.x * w), int(idx_tip.y * h)
                mx, my = int(mid_tip.x * w), int(mid_tip.y * h)
                tx, ty = int(thumb_tip.x * w), int(thumb_tip.y * h)

                # Glow
                overlay = frame.copy()
                for radius, alpha in [(40, 0.1), (25, 0.2), (12, 0.3)]:
                    cv2.circle(overlay, (cx, cy), radius, current_color, -1)
                frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
                cv2.circle(frame, (cx, cy), 6, (255, 255, 255), -1)

                # Button press
                pressed = check_button_press(cx, cy, buttons)
                if pressed == "Draw":
                    draw_enabled = not draw_enabled
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

                # Gesture distances
                dist_thumb = distance((cx, cy), (tx, ty))
                dist_idx_mid = distance((cx, cy), (mx, my))

                # Draw only if draw_enabled and pinching
                if draw_enabled and dist_thumb < PINCH_THRESHOLD:
                    drawing = True
                else:
                    drawing = False

                # Smooth color change with cooldown
                now = time.time()
                if dist_idx_mid < COLOR_CHANGE_THRESHOLD and now - last_color_change_time > COLOR_COOLDOWN:
                    color_index = (color_index + 1) % len(palette)
                    current_color = palette[color_index]
                    last_color_change_time = now
                    cv2.putText(frame, "Color Changed!", (cx+30, cy-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, current_color, 2)

                # Actual drawing
                if drawing:
                    if prev_point:
                        cv2.line(canvas, prev_point, (cx, cy), current_color, 8)
                    prev_point = (cx, cy)
                else:
                    prev_point = None

        frame = cv2.addWeighted(frame, 0.7, canvas, 1, 0)
        draw_buttons(frame, buttons, draw_enabled)
        cv2.putText(frame, "Hold Pinch to Draw | Index+Middle = Color | ESC=Exit",
                    (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

        cv2.imshow("Natural Air Drawing", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break
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
