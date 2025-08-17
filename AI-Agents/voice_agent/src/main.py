#!/usr/bin/env python
import sys
import warnings
import os
import argparse

from datetime import datetime

#from voice_crew.crew import VoiceCrew
# Use relative import instead
from voice_crew.video_feed.video_feed import capture_frame, capture_frame_with_voice, ensure_recordings_directory

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run(with_voice=True, save_mode=False):
    """
    Run the crew.
    
    Args:
        with_voice (bool): If True, use capture_frame_with_voice instead of capture_frame
        save_mode (bool): If True, directories are created and recordings are saved
    """
    inputs = {
        'topic': 'AI LLMs',
        'current_year': str(datetime.now().year)
    }
    
    try:
        # Create recording directories and get paths before starting capture
        session_dir, frames_dir, audio_dir, temp_dir = ensure_recordings_directory()
        print(f"Recording session started. Files will be saved to:")
        print(f"  - Session directory: {session_dir}")
        print(f"  - Frames directory:  {frames_dir}")
        print(f"  - Audio directory:   {audio_dir}")
        print(f"  - Temp directory:    {temp_dir}")
        
        if with_voice:
            print("\nStarting video feed with voice recognition. Press 'q' to proceed with CrewAI.")
            last_frame = capture_frame_with_voice(save_mode=save_mode)  # This will show video feed with voice recognition
        else:
            print("\nStarting video feed. Press 'q' to proceed with CrewAI.")
            last_frame = capture_frame()  # This will show video feed and return last frame
            
        inputs['last_frame'] = last_frame  # Add captured frame to inputs for CrewAI
        
        print(f"\nSession completed. All recordings saved to {session_dir}")
        
        # Uncomment when ready to integrate with CrewAI
        # VoiceCrew().crew().kickoff(inputs=inputs)
        
    except Exception as e:
        print(f"An error occurred: {e}")
    """
    try:     
    7# VoiceCrew().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")
    """


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "topic": "AI LLMs"
    }
    try:
        print("training")
        #VoiceCrew().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        print("replaying")
        #VoiceCrew().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }
    try:
        print("testing")
        # VoiceCrew().crew().test(n_iterations=int(sys.argv[1]), openai_model_name=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Voice Crew AI with video and audio recording.')
    parser.add_argument('--no-voice', action='store_true', 
                        help='Disable voice recognition (captures video only without audio)')
    parser.add_argument('--save-audio', action='store_true',
                        help='Save mode (--save-audio) creates directories and saves all recordings. Default mode only shows real-time display without saving files.')
    
    # Parse arguments and run with voice by default
    if len(sys.argv) > 1:
        args = parser.parse_args()
        run(with_voice=not args.no_voice, save_mode=args.save_audio)
    else:
        run()
