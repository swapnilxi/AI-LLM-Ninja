import cv2
from PIL import Image
import logging
import os
import sys
import time
import threading
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
import whisper
from queue import Queue
import queue
import datetime
import json
from voice_crew.tools.browser_control import perform_google_search
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def ensure_recordings_directory():
    """
    Ensures the recordings directory exists and returns its path.
    Creates a timestamped subfolder for each session and a temp directory.
    """
    # Create base recordings directory if it doesn't exist
    recordings_dir = os.path.join(os.getcwd(), "recordings")
    if not os.path.exists(recordings_dir):
        os.makedirs(recordings_dir)
        logger.info(f"Created recordings directory at {recordings_dir}")
    
    # Create temp directory for temporary files
    temp_dir = os.path.join(recordings_dir, "temp")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        logger.info(f"Created temp directory at {temp_dir}")
    
    # Create timestamped subfolder for this session
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(recordings_dir, f"session_{timestamp}")
    
    if not os.path.exists(session_dir):
        os.makedirs(session_dir)
        logger.info(f"Created session directory at {session_dir}")
    
    # Create separate folders for frames and audio
    frames_dir = os.path.join(session_dir, "frames")
    audio_dir = os.path.join(session_dir, "audio")
    
    if not os.path.exists(frames_dir):
        os.makedirs(frames_dir)
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)
    
    return session_dir, frames_dir, audio_dir, temp_dir
def cleanup_temp_files(temp_dir):
    """
    Clean up temporary files in the temp directory.
    """
    try:
        if os.path.exists(temp_dir):
            count = 0
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    count += 1
            logger.info(f"Cleaned up {count} temporary files from {temp_dir}")
    except Exception as e:
        logger.error(f"Error cleaning up temporary files: {str(e)}")

def capture_frame():
    """
    Captures and displays continuous video feed until 'q' is pressed
    """
    logger.info("Starting video capture function")
    frame = None
    
    # Ensure recording directories exist
    session_dir, frames_dir, audio_dir, temp_dir = ensure_recordings_directory()
    
    try:
        logger.info("Initializing camera (webcam index 0)")
        cap = cv2.VideoCapture(0)  # Webcam feed
        
        if not cap.isOpened():
            logger.error("Failed to access the camera")
            raise Exception("Could not access the camera")
        
        logger.info("Camera successfully initialized")
        
        # Log camera properties
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        logger.info(f"Camera properties: Resolution={width}x{height}, FPS={fps}")
        
        frame_count = 0
        start_time = time.time()
        logger.info("Video feed started. Press 'q' to quit.")
        
        # For periodic frame saving
        save_interval = 120  # Save a frame every 120 frames
        
        while True:
            try:
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to capture frame")
                    # Try to reconnect to the camera
                    logger.info("Attempting to reconnect to camera...")
                    cap.release()
                    cap = cv2.VideoCapture(0)
                    if not cap.isOpened():
                        logger.error("Failed to reconnect to camera")
                        break
                    continue
                
                frame_count += 1
                if frame_count % 30 == 0:  # Log every 30 frames
                    elapsed = time.time() - start_time
                    logger.info(f"Captured {frame_count} frames ({frame_count/elapsed:.2f} fps)")
                
                # Save frames periodically
                if frame_count % save_interval == 0:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    frame_filename = os.path.join(frames_dir, f"frame_{timestamp}.jpg")
                    cv2.imwrite(frame_filename, frame)
                    logger.info(f"Saved frame to {frame_filename}")
                
                # Display the frame
                cv2.imshow('AI Agent Camera Feed', frame)
                
                # Break the loop when 'q' is pressed
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    logger.info("User pressed 'q' - stopping video feed")
                    break
                
            except Exception as e:
                logger.error(f"Error during frame capture: {str(e)}")
                continue
        
        # Clean up
        logger.info("Releasing camera and cleaning up resources")
        cap.release()
        cv2.destroyAllWindows()
        cleanup_temp_files(temp_dir)
        
        if frame is not None:
            try:
                # Save the last frame for potential use by CrewAI
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(frames_dir, f"last_frame_{timestamp}.jpg")
                logger.info(f"Saving last frame to {filename}")
                cv2.imwrite(filename, frame)
                logger.info(f"Successfully saved frame to {filename}")
                
                # Also save a copy as frame.jpg in the session directory for backward compatibility
                compat_filename = os.path.join(session_dir, 'frame.jpg')
                cv2.imwrite(compat_filename, frame)
                
                return Image.open(filename)
            except Exception as e:
                logger.error(f"Error saving or opening the captured frame: {str(e)}")
                return None
        else:
            logger.warning("No valid frame was captured")
            return None
            
    except Exception as e:
        logger.error(f"Critical error in video capture: {str(e)}")
        # Clean up in case of exception
        try:
            if 'cap' in locals() and cap is not None:
                cap.release()
            cv2.destroyAllWindows()
            if 'temp_dir' in locals():
                cleanup_temp_files(temp_dir)
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {str(cleanup_error)}")
        return None
    finally:
        logger.info("Video capture function completed")

def list_audio_devices():
    """
    List all available audio input devices.
    Returns a list of (device_id, device_name) tuples.
    """
    devices = sd.query_devices()
    input_devices = []
    
    logger.info("Available audio input devices:")
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:  # This is an input device
            input_devices.append((i, device['name']))
            logger.info(f"  {i}: {device['name']}")
    
    return input_devices

def get_device_id(device_input):
    """
    Get the device ID from the input, which could be:
    - An integer device ID
    - A string device name
    - None (will return None to use system default)
    
    Returns the device ID or None if not found
    """
    if device_input is None:
        return None
        
    if isinstance(device_input, int):
        return device_input
        
    if isinstance(device_input, str):
        # Try to find a device with this name
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0 and device_input.lower() in device['name'].lower():
                logger.info(f"Found device '{device['name']}' with ID {i} for input '{device_input}'")
                return i
        
        logger.warning(f"No input device found matching '{device_input}'. Using system default.")
    
    return None
def capture_frame_with_voice(device=4, save_mode=False):
    """
    Captures and displays continuous video feed while simultaneously
    listening for voice input and transcribing it in near real-time.
    
    Args:
        device: Audio input device to use. Can be:
                - A string name of the device (will use partial matching)
                - An integer device ID
                - None to use system default
                Default is 4 (External Earphones)
        save_mode: Whether to save frames, audio, and transcriptions to disk.
                   If False, only displays real-time feed without saving files.
                   Default is False.
    """
    logger.info(f"Starting video capture with voice recognition (save_mode: {save_mode})")
    frame = None
    transcription_queue = Queue()
    audio_buffer_queue = queue.Queue()  # Queue for audio buffers to be transcribed
    
    # Get device ID from the device parameter
    device_id = get_device_id(device)
    if device_id is not None:
        logger.info(f"Using audio input device ID: {device_id}")
    else:
        logger.info("Using system default audio input device")
        
    # List available devices for reference
    list_audio_devices()
    
    # Initialize directory variables
    session_dir = frames_dir = audio_dir = temp_dir = None
    transcriptions_file = None
    
    # Ensure recording directories exist (always need the temp directory)
    session_dir, frames_dir, audio_dir, temp_dir = ensure_recordings_directory()
    
    # Only setup for saving files if save_mode is enabled
    if save_mode:
        
        # Create a file to store all transcriptions
        transcriptions_file = os.path.join(session_dir, "transcriptions.txt")
        logger.info(f"Save mode enabled. Files will be saved to {session_dir}")
    else:
        logger.info("Save mode disabled. No files will be saved.")
    
    # Add a threading event to signal thread termination
    stop_event = threading.Event()
    
    # Load Whisper model
    try:
        logger.info("Loading Whisper model...")
        model = whisper.load_model("base")  # Changed from "base" to "tiny" for faster processing
        logger.info("Whisper model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {str(e)}")
        return None
    
    # Audio recording parameters optimized for speech recognition
    fs = 16000  # Sample rate (standard for speech recognition)
    duration = 1  # Further reduced duration for even faster response
    
    # Function to continuously record audio and add to buffer queue
    def record_audio():
        nonlocal device_id
        while not stop_event.is_set():
            try:
                # Record smaller audio chunks for more responsive processing
                audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, device=device_id)
                
                # Check if stop was requested during recording
                if stop_event.wait(timeout=duration):
                    logger.info("Audio recording interrupted for clean shutdown")
                    break
                
                # Wait to ensure recording is complete
                sd.wait()
                
                # If stop event was set during wait, exit
                if stop_event.is_set():
                    break
                
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                audio_file = None
                
                # Save audio to file with timestamp if save_mode is enabled
                if save_mode:
                    audio_file = os.path.join(audio_dir, f'audio_{timestamp}.wav')
                    write(audio_file, fs, audio)
                    logger.info(f"Saved audio to {audio_file}")
                
                # Add audio data to buffer queue for processing
                # If save_mode is False, pass the audio data directly instead of a file path
                if save_mode:
                    audio_buffer_queue.put((timestamp, audio_file))
                else:
                    # Create a temporary file in the temp directory for processing
                    temp_file = os.path.join(temp_dir, f'temp_audio_{timestamp}.wav')
                    write(temp_file, fs, audio)
                    audio_buffer_queue.put((timestamp, temp_file))
                
            except Exception as e:
                logger.error(f"Error in audio recording thread: {str(e)}")
                if stop_event.is_set():
                    break
    
    # Function to transcribe audio from buffer queue
    def transcribe_audio():
        while not stop_event.is_set():
            try:
                # Get audio file from buffer queue with timeout to check stop_event regularly
                try:
                    timestamp, audio_file = audio_buffer_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # If stop event was set, exit
                if stop_event.is_set():
                    break
                
                # Transcribe the audio
                logger.info(f"Transcribing audio file {audio_file}...")
                result = model.transcribe(audio_file)
                transcription = result["text"].strip()
                
                if transcription:
                    logger.info(f"Transcription: {transcription}")
                    transcription_queue.put((datetime.datetime.now(), transcription, audio_file))
                    
                    # Save transcription to file if save_mode is enabled
                    if save_mode and transcriptions_file:
                        with open(transcriptions_file, 'a') as f:
                            f.write(f"{timestamp}: {transcription}\n")
                
                # Mark task as done
                audio_buffer_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in transcription thread: {str(e)}")
                if stop_event.is_set():
                    break
                
                # Clean up temporary files if not in save_mode
                if not save_mode and os.path.exists(audio_file):
                    try:
                        os.remove(audio_file)
                    except Exception as e:
                        logger.debug(f"Error removing temporary file {audio_file}: {str(e)}")
    
    try:
        logger.info("Initializing camera (webcam index 0)")
        cap = cv2.VideoCapture(0)  # Webcam feed
        
        if not cap.isOpened():
            logger.error("Failed to access the camera")
            raise Exception("Could not access the camera")
        
        logger.info("Camera successfully initialized")
        
        # Log camera properties
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        logger.info(f"Camera properties: Resolution={width}x{height}, FPS={fps}")
        
        # Start the audio recording and transcription threads
        audio_thread = threading.Thread(target=record_audio, daemon=True)
        transcription_thread = threading.Thread(target=transcribe_audio, daemon=True)
        
        audio_thread.start()
        transcription_thread.start()
        logger.info("Audio recording and transcription threads started")
        
        frame_count = 0
        start_time = time.time()
        logger.info("Video feed started. Press 'q' to quit.")
        
        # Store recent transcriptions to display on screen
        recent_transcriptions = []
        max_transcriptions = 5  # Maximum number of transcriptions to display
        
        # Variables for search functionality
        search_mode = False
        search_start_time = None
        search_wait_duration = 2.5  # Wait 2.5 seconds after "search" command
        search_query = ""
        
        # For periodic frame saving
        save_interval = 120  # Save a frame every 120 frames
        
        while True:
            try:
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to capture frame")
                    # Try to reconnect to the camera
                    logger.info("Attempting to reconnect to camera...")
                    cap.release()
                    cap = cv2.VideoCapture(0)
                    if not cap.isOpened():
                        logger.error("Failed to reconnect to camera")
                        break
                    continue
                
                frame_count += 1
                if frame_count % 30 == 0:  # Log every 30 frames
                    elapsed = time.time() - start_time
                    logger.info(f"Captured {frame_count} frames ({frame_count/elapsed:.2f} fps)")
                
                # Save frames periodically if save_mode is enabled
                if save_mode and frame_count % save_interval == 0:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    frame_filename = os.path.join(frames_dir, f"frame_{timestamp}.jpg")
                    cv2.imwrite(frame_filename, frame)
                    logger.info(f"Saved frame to {frame_filename}")
                
                # Check for new transcriptions
                # Check for new transcriptions
                while not transcription_queue.empty():
                    timestamp, text, audio_file = transcription_queue.get()
                    recent_transcriptions.append((timestamp, text, audio_file))
                    
                    # Process search commands
                    if search_mode:
                        # We're already in search mode, capturing the query
                        current_time = time.time()
                        # Check if we've waited long enough after "search" command
                        if current_time - search_start_time >= search_wait_duration:
                            # Add the transcribed text to the search query
                            search_query += " " + text
                            # Execute the search after gathering query
                            logger.info(f"Executing search with query: {search_query}")
                            try:
                                perform_google_search(search_query)
                                # Add a confirmation to recent transcriptions
                                confirmation = f"Searching for: {search_query}"
                                recent_transcriptions.append((datetime.datetime.now(), confirmation, None))
                            except Exception as e:
                                logger.error(f"Failed to execute browser search: {str(e)}")
                                recent_transcriptions.append((datetime.datetime.now(), f"Search failed: {str(e)}", None))
                            # Reset search mode
                            search_mode = False
                            search_query = ""
                    elif "search" in text.lower():
                        # Entering search mode
                        logger.info("Search command detected, waiting for query...")
                        search_mode = True
                        search_start_time = time.time()
                        # Extract any text after "search" as the beginning of the query
                        search_parts = text.lower().split("search", 1)
                        if len(search_parts) > 1 and search_parts[1].strip():
                            search_query = search_parts[1].strip()
                        else:
                            search_query = ""
                        # Add a notification to recent transcriptions
                        recent_transcriptions.append((datetime.datetime.now(), "Search mode activated, listening for query...", None))
                    
                    # Also save a frame when a transcription is made if save_mode is enabled
                    if save_mode:
                        transcription_frame_filename = os.path.join(frames_dir, f"transcription_frame_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg")
                        cv2.imwrite(transcription_frame_filename, frame)
                        logger.info(f"Saved frame with transcription to {transcription_frame_filename}")
                    
                    # Keep only the most recent transcriptions
                    if len(recent_transcriptions) > max_transcriptions:
                        recent_transcriptions.pop(0)
                # Create a copy of the frame for displaying
                display_frame = frame.copy()
                
                # Add transcriptions to the frame
                y_offset = 30
                for i, (timestamp, text, _) in enumerate(recent_transcriptions):
                    time_str = timestamp.strftime("%H:%M:%S")
                    text_to_display = f"{time_str}: {text}"
                    
                    # Add a semi-transparent background for text
                    text_size = cv2.getTextSize(text_to_display, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                    cv2.rectangle(display_frame, 
                                 (10, y_offset - 25), 
                                 (10 + text_size[0], y_offset + 5), 
                                 (0, 0, 0, 0.5), 
                                 -1)
                    
                    # Add the text
                    cv2.putText(display_frame, 
                               text_to_display, 
                               (10, y_offset), 
                               cv2.FONT_HERSHEY_SIMPLEX, 
                               0.7, 
                               (255, 255, 255), 
                               2, 
                               cv2.LINE_AA)
                    y_offset += 30
                
                # Show a recording indicator
                cv2.circle(display_frame, (int(width) - 30, 30), 10, (0, 0, 255), -1)
                cv2.putText(display_frame, 
                           "Real-time audio", 
                           (int(width) - 140, 35), 
                           cv2.FONT_HERSHEY_SIMPLEX, 
                           0.6, 
                           (255, 255, 255), 
                           1, 
                           cv2.LINE_AA)
                
                # Display the frame
                cv2.imshow('AI Agent Camera Feed with Voice Recognition', display_frame)
                
                # Break the loop when 'q' is pressed
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    logger.info("User pressed 'q' - stopping video and audio feed")
                    break
                
            except Exception as e:
                logger.error(f"Error during frame capture: {str(e)}")
                continue
        
        # Clean up
        # Clean up
        logger.info("Releasing camera and cleaning up resources")
        # Signal the audio thread to stop
        stop_event.set()
        # Clean up any temporary files
        cleanup_temp_files(temp_dir)
        logger.info("Waiting for audio recording and transcription threads to terminate...")
        audio_thread.join(timeout=2.0)  # Give it 2 seconds to clean up
        transcription_thread.join(timeout=2.0)  # Give it 2 seconds to clean up
        
        # Release camera resources
        cap.release()
        cv2.destroyAllWindows()
        
        if frame is not None:
            try:
                if save_mode:
                    # Save the last frame for potential use by CrewAI
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = os.path.join(frames_dir, f"last_frame_{timestamp}.jpg")
                    logger.info(f"Saving last frame to {filename}")
                    cv2.imwrite(filename, frame)
                    logger.info(f"Successfully saved frame to {filename}")
                    
                    # Also save a copy as frame.jpg in the session directory for backward compatibility
                    compat_filename = os.path.join(session_dir, 'frame.jpg')
                    cv2.imwrite(compat_filename, frame)
                    
                    return Image.open(filename)
                else:
                    # In no-save mode, convert the frame to PIL Image without saving to disk
                    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            except Exception as e:
                logger.error(f"Error saving or opening the captured frame: {str(e)}")
                return None
        else:
            logger.warning("No valid frame was captured")
            return None
            
    except Exception as e:
        logger.error(f"Critical error in video and voice capture: {str(e)}")
        # Clean up in case of exception
        try:
            # Signal the audio thread to stop
            stop_event.set()
            
            if 'audio_thread' in locals() and audio_thread.is_alive():
                audio_thread.join(timeout=1.0)
                
            if 'transcription_thread' in locals() and transcription_thread.is_alive():
                transcription_thread.join(timeout=1.0)
                transcription_thread.join(timeout=1.0)
                
            if 'cap' in locals() and cap is not None:
                cap.release()
            cv2.destroyAllWindows()
            
            # Clean up temporary files
            cleanup_temp_files(temp_dir)
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {str(cleanup_error)}")
        return None
    finally:
        # Make absolutely sure the stop event is set
        stop_event.set()
        # Final cleanup check
        if 'temp_dir' in locals() and temp_dir:
            cleanup_temp_files(temp_dir)
        logger.info("Video and voice capture function completed")
