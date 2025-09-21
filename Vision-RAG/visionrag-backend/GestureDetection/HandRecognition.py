import cv2
import mediapipe as mp
import numpy as np 
import time 

cap = cv2.VideoCapture(0)
mpHands = mp.solutions.hands
hands = mpHands.Hands()
mpDraw= mp.solutions.drawing_utils  


while True:
    success, img = cap.read()
    imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hands.process(imgRGB)
    #print(results.multi_hand_landmarks)
    
    #multiple hands
    if results.multi_hand_landmarks:
        for handLms in results.multi_hand_landmarks:
            for id , lm in enumerate(handLms.landmark):
                #print(id,lm)
                h,w,c= img.shape
                cx, cy = int(lm.x * w), int(lm.y * h)
                print(id, cx, cy)
                #comment id for all
                if id == 4:
                    cv2.circle(img, (cx,cy), 15, (255,0,255), cv2.FILLED) 
            mpDraw.draw_landmarks(img, handLms,mp.hands.HAND_CONNECTIONS)
            

#hand_frame_rate
    ctime = time.time()
    fps = 1/(ctime - ptime)
    ptime = ctime
    
   # cv2.putText(img, text, position, fontFace, fontScale, color[, thickness) 
    cv2.putText(img, str(int(fps)), (10,70), cv2.FONT_HERSHEY_PLAIN, 3, (255,0,255), 3)
    
    
            
    
    cv2.imshow("Image", img)
    cv2.waitKey(1) 