import cv2
import numpy as np
import time
from pathlib import Path

class InputLayer:
    """
    Handles:
    - Webcam capture (with graceful fallback)
    - Fallback image when camera unavailable
    - Frame resizing
    - Automatic recovery if webcam disconnects

    Acts as a unified provider for each frame of the pipeline.
    """

    def __init__(self, fallback_path: str, desired_width=1280, desired_height=720):
        self.fallback_path = Path(fallback_path)
        self.desired_w = desired_width
        self.desired_h = desired_height

        self.cap = None
        self.camera_ok = False

        self._load_fallback()
        self._init_camera()

    # ----------------------------------------------------
    # Internal Helpers
    # ----------------------------------------------------

    def _load_fallback(self):
        if not self.fallback_path.exists():
            raise FileNotFoundError(
                f"Fallback image not found at {self.fallback_path}"
            )
        self.fallback_img = cv2.imread(str(self.fallback_path))
        if self.fallback_img is None:
            raise ValueError("Could not load fallback image file")

        self.fallback_img = cv2.resize(
            self.fallback_img,
            (self.desired_w, self.desired_h),
            interpolation=cv2.INTER_AREA
        )

    def _init_camera(self):
        """Initialize webcam and check if working."""
        try:
            self.cap = cv2.VideoCapture(0)
            self.camera_ok = self.cap.isOpened()
        except:
            self.camera_ok = False

        if not self.camera_ok:
            print("[InputLayer] Camera unavailable → using fallback mode.")

    # ----------------------------------------------------
    # Public API
    # ----------------------------------------------------

    def get_frame(self):
        """
        Returns:
        - A frame (numpy array)
        - Source type: "camera" or "fallback"
        """
        if self.camera_ok:
            ret, frame = self.cap.read()

            if not ret:
                # Camera failed mid-run → fallback + try to reconnect
                print("[InputLayer] Camera frame not received. Switching to fallback.")
                self.camera_ok = False
                return self.fallback_img.copy(), "fallback"

            frame = cv2.resize(
                frame, (self.desired_w, self.desired_h),
                interpolation=cv2.INTER_AREA
            )
            return frame, "camera"

        else:
            # Try reinitializing camera every second
            if np.random.rand() < 0.01:
                self._init_camera()

            return self.fallback_img.copy(), "fallback"

    def release(self):
        """Release camera safely."""
        if self.cap and self.camera_ok:
            self.cap.release()
