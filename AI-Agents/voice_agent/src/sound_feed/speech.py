import whisper
import sounddevice as sd
from scipy.io.wavfile import write
import pyttsx3

model = whisper.load_model("base")

def transcribe_voice(duration=5, fs=44100):
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    write('input.wav', fs, audio)
    result = model.transcribe('input.wav')
    return result["text"]


def speak_text(text):
    engine = pyttsx3.init()
    engine.say(f'So here is the question you asked {text}')
    engine.say('please wait while I process the answer')
    engine.runAndWait()