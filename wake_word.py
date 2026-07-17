import os
import struct
import time

import pvporcupine
import pyaudio
import requests
import speech_recognition as sr
from dotenv import load_dotenv


BASE_URL = "http://127.0.0.1:8000"
WAKE_WORD_FILE = "Hello-STAR_en_windows_v4_0_0.ppn"

load_dotenv()

porcupine = pvporcupine.create(
    access_key=os.getenv("PICOVOICE_ACCESS_KEY"),
    keyword_paths=[WAKE_WORD_FILE],
)

pa = pyaudio.PyAudio()
recognizer = sr.Recognizer()
recognizer.pause_threshold = 0.8
recognizer.non_speaking_duration = 0.5
recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True

conversation_mode = False
audio_stream = None


def open_wake_stream():
    return pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length,
    )


def call_star(path, params=None):
    try:
        return requests.get(f"{BASE_URL}{path}", params=params, timeout=20)
    except requests.RequestException as exc:
        print("STAR backend request failed:", exc)
        return None


def is_stop_command(text):
    stop_words = ["stop", "stop it", "shut up", "be quiet", "pause"]
    return any(word in text for word in stop_words)


def is_exit_command(text):
    exit_words = [
        "goodbye",
        "good bye",
        "bye",
        "bye star",
        "exit",
        "sleep",
        "go to sleep",
    ]
    return any(word in text for word in exit_words)


def listen_continuous():
    global audio_stream, conversation_mode

    audio_stream.stop_stream()
    audio_stream.close()
    time.sleep(0.5)

    while conversation_mode:
        with sr.Microphone() as source:
            print("Listening Bajrangi...")
            recognizer.adjust_for_ambient_noise(source, duration=0.3)

            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=4)
            except sr.WaitTimeoutError:
                continue

        try:
            command = recognizer.recognize_google(audio).lower().strip()
        except sr.UnknownValueError:
            print("Not understood")
            continue
        except Exception as exc:
            print("Speech recognition error:", exc)
            continue

        print("You said:", command)

        if is_stop_command(command):
            print("Stopping speech...")
            call_star("/stop")
            continue

        if is_exit_command(command):
            print("Exiting conversation mode.")
            conversation_mode = False
            break

        call_star("/ask-star", params={"q": command})

    audio_stream = open_wake_stream()


def main():
    global audio_stream, conversation_mode

    audio_stream = open_wake_stream()
    print("STAR is listening for wake word...")

    while True:
        pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
        pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

        keyword_index = porcupine.process(pcm)
        if keyword_index >= 0:
            print("Wake word detected!")
            conversation_mode = True
            listen_continuous()


if __name__ == "__main__":
    try:
        main()
    finally:
        if audio_stream:
            audio_stream.close()
        pa.terminate()
        porcupine.delete()
