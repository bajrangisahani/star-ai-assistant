import subprocess
import webbrowser
from urllib.parse import quote_plus

import pyautogui


def play_pause():
    pyautogui.press("playpause")
    return "Toggled play or pause."


def next_track():
    pyautogui.press("nexttrack")
    return "Next track."


def previous_track():
    pyautogui.press("prevtrack")
    return "Previous track."


def stop_media():
    pyautogui.press("stop")
    return "Stopped media."


def open_youtube(query=None):
    if query:
        webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(query)}")
        return f"Searching YouTube for {query}."

    webbrowser.open("https://www.youtube.com")
    return "Opening YouTube."


def open_spotify(query=None):
    try:
        subprocess.Popen('start "" spotify:', shell=True)
        if query:
            return f"Opening Spotify. Search for {query} when it opens."
        return "Opening Spotify."
    except Exception:
        webbrowser.open("https://open.spotify.com")
        return "Opening Spotify web."


def open_netflix():
    webbrowser.open("https://www.netflix.com")
    return "Opening Netflix."


def open_vlc():
    try:
        subprocess.Popen('start "" vlc', shell=True)
        return "Opening VLC."
    except Exception:
        return "VLC was not found."


def handle_media_command(command):
    text = command.lower().strip()

    if "youtube" in text:
        query = text.replace("open youtube", "").replace("play youtube", "").replace("youtube", "").strip()
        return open_youtube(query or None)

    if "spotify" in text:
        query = text.replace("open spotify", "").replace("play spotify", "").replace("spotify", "").strip()
        return open_spotify(query or None)

    if "netflix" in text:
        return open_netflix()

    if "vlc" in text:
        return open_vlc()

    if any(phrase in text for phrase in ["play pause", "pause music", "play music", "pause media", "resume media"]):
        return play_pause()

    if any(phrase in text for phrase in ["next song", "next track", "next media"]):
        return next_track()

    if any(phrase in text for phrase in ["previous song", "previous track", "prev song"]):
        return previous_track()

    if any(phrase in text for phrase in ["stop music", "stop media"]):
        return stop_media()

    return None
