#!/usr/bin/env python3
"""
Test script for video capture with voice recognition.
This program captures video from the camera and simultaneously records audio for transcription.
"""

import logging
import sys
from video_feed import capture_frame_with_voice

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    Main function that runs the video and voice capture test.
    """
    print("=" * 70)
    print("Video and Voice Capture Test")
    print("=" * 70)
    print("This program will capture both video from your camera and audio from your microphone.")
    print("Your voice will be transcribed and displayed on the video feed in real-time.")
    print("Note: Audio is recorded in 5-second intervals for transcription.")
    print("\nPress 'q' at any time to stop the program and exit.")
    print("=" * 70)
    
    # Run the video and voice capture function
    result = capture_frame_with_voice()
    
    if result:
        logger.info("Successfully captured and saved the last frame")
    else:
        logger.warning("No frame was saved or an error occurred")

if __name__ == "__main__":
    main()

