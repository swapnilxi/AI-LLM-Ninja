import cv2

# Initialize camera capture (0 is usually the default webcam index)
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Could not open webcam. Falling back to voice-only mode.")

while True:
    ret, frame = cap.read()
    if not ret:
        break  # End loop if frame not read
    # (Optional) Resize or preprocess the frame for faster processing
    small_frame = cv2.resize(frame, (640, 480))
    # ... (we will process the frame with BLIP-2 in the next steps)
    cv2.imshow("Camera Feed", small_frame)  # Display the video feed (for testing)
    if cv2.waitKey(1) & 0xFF == 27:  # Exit on pressing 'Esc'
        break

cap.release()
cv2.destroyAllWindows()
