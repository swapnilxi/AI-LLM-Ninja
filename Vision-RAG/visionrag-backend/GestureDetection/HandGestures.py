import cv2
import numpy as np
import time 
import os 
import mediapipe as mp
import handtrackmodule as htm

folderPath = "GestureImages"
myList = os.listdir(folderPath) 