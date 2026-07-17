import os
import struct
import time

import pvporcupine
import pyaudio
import requests
import speech_recognition as sr
from dotenv import load_dotenv

import star_voice


BASE_URL = "http://127.0.0.1:8000"
WAKE_WORD_FILE = "Hello-STAR_en_windows_v4_0_0.ppn"

load_dotenv()

porcupine = pvporcupine.create(
    access_key=os.getenv("PICOVOICE_ACCESS_KEY"),
    keyword_paths=[WAKE_WORD_FILE],
)

pa = pyaudio.PyAudio()
recognizer = sr.Recognizer()
recognizer.non_speaking_duration = 0.5
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


def apply_voice_settings(settings=None):
    settings = settings or star_voice.get_settings()
    recognizer.pause_threshold = float(settings.get("voice_pause_threshold", "0.8"))
    recognizer.energy_threshold = int(float(settings.get("voice_energy_threshold", "300")))
    return settings


apply_voice_settings()


def call_star(path, params=None, method="get"):
    try:
        request = requests.post if method == "post" else requests.get
        return request(f"{BASE_URL}{path}", params=params, timeout=20)
    except requests.RequestException as exc:
        print("STAR backend request failed:", exc)
        return None


def recognize_with_fallback(audio, settings):
    errors = []
    for language in star_voice.recognition_languages(settings):
        try:
            transcript = recognizer.recognize_google(audio, language=language)
            return star_voice.clean_transcript(transcript), language
        except sr.UnknownValueError:
            errors.append(language)
        except Exception as exc:
            print(f"Speech recognition error for {language}:", exc)
            errors.append(language)
    print("Not understood with languages:", ", ".join(errors))
    return "", None


def listen_continuous():
    global audio_stream, conversation_mode

    audio_stream.stop_stream()
    audio_stream.close()
    time.sleep(0.5)

    while conversation_mode:
        settings = apply_voice_settings()
        with sr.Microphone() as source:
            print("Listening Bajrangi...")
            recognizer.adjust_for_ambient_noise(source, duration=0.3)

            try:
                audio = recognizer.listen(
                    source,
                    timeout=int(float(settings.get("voice_timeout", "5"))),
                    phrase_time_limit=int(float(settings.get("voice_phrase_time_limit", "6"))),
                )
            except sr.WaitTimeoutError:
                continue

        command, used_language = recognize_with_fallback(audio, settings)
        if not command:
            continue

        print(f"You said ({used_language}):", command)

        if star_voice.is_stop_speaking_command(command):
            print("Stopping speech...")
            call_star("/stop")
            continue

        if star_voice.is_repeat_command(command):
            print("Repeating last reply...")
            call_star("/voice/repeat", method="post")
            continue

        confirmation = star_voice.confirmation_intent(command)
        if confirmation:
            print("Confirmation intent:", confirmation)
            call_star("/ask-star", params={"q": confirmation})
            continue

        if star_voice.is_exit_listening_command(command):
            print("Exiting conversation mode.")
            conversation_mode = False
            break

        response = call_star("/ask-star", params={"q": command})
        if response is not None:
            try:
                reply = response.json().get("reply", "")
                star_voice.remember_interaction(command, reply)
            except ValueError:
                pass

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
