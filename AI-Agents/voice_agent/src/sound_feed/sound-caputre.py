import pyaudio
import numpy as np

# Initialize PyAudio and open input stream
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)

audio_frames = []
print("Listening...")

# Record a chunk of audio (e.g., 3 seconds or until silence is detected)
for _ in range(0, int(16000 / 1024 * 3)):  # ~3 seconds
    data = stream.read(1024)
    audio_frames.append(data)

# Stop the stream after capturing the chunk
stream.stop_stream()
stream.close()
p.terminate()

# Convert audio frames to numpy array for STT
audio_data = np.frombuffer(b''.join(audio_frames), dtype=np.int16).astype(np.float32) / 32768.0
