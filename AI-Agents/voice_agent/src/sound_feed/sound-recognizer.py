import whisper
import sounddevice as sd
from scipy.io.wavfile import write

# Record audio
fs = 44100  # Sample rate
seconds = 5  # Duration
audio = sd.rec(int(seconds * fs), samplerate=fs, channels=1)
sd.wait()
write('input.wav', fs, audio)

# Transcribe audio
model = whisper.load_model("base")
result = model.transcribe('input.wav')
#result = model.transcribe(audio_data, fp16=False)
transcript = result["text"].strip()
print("User said:", transcript)



