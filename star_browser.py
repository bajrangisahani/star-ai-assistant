import mimetypes
import re
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import pyautogui
import requests


DOWNLOADS_DIR = Path.home() / "Downloads"


def normalize_url(target):
    value = str(target).strip()
    if not value:
        return ""

    parsed = urlparse(value)
    if parsed.scheme:
        return value

    if "." in value and " " not in value:
        return "https://" + value

    return "https://www.google.com/search?q=" + quote_plus(value)


def open_website(target):
    url = normalize_url(target)
    if not url:
        return "Tell me which website to open."

    webbrowser.open(url)
    return f"Opening {target}."


def search_google(query):
    clean = str(query).strip()
    if not clean:
        return "Tell me what to search."
    webbrowser.open(f"https://www.google.com/search?q={quote_plus(clean)}")
    return f"Searching Google for {clean}."


def search_duckduckgo(query):
    clean = str(query).strip()
    if not clean:
        return "Tell me what to search."
    webbrowser.open(f"https://duckduckgo.com/?q={quote_plus(clean)}")
    return f"Searching DuckDuckGo for {clean}."


def new_tab(target=None):
    if target:
        webbrowser.open_new_tab(normalize_url(target))
        return "Opened a new tab."

    pyautogui.hotkey("ctrl", "t")
    return "Opened a new tab."


def close_tab():
    pyautogui.hotkey("ctrl", "w")
    return "Closed current tab."


def next_tab():
    pyautogui.hotkey("ctrl", "tab")
    return "Moved to next tab."


def previous_tab():
    pyautogui.hotkey("ctrl", "shift", "tab")
    return "Moved to previous tab."


def refresh_page():
    pyautogui.hotkey("ctrl", "r")
    return "Page refreshed."


def focus_address_bar():
    pyautogui.hotkey("ctrl", "l")
    return "Address bar focused."


def open_downloads_page():
    webbrowser.open("chrome://downloads")
    return "Opening browser downloads."


def download_file(url, folder=None):
    clean_url = normalize_url(url)
    parsed = urlparse(clean_url)
    if not parsed.scheme or parsed.scheme not in {"http", "https"}:
        return {"error": "Only http and https downloads are supported."}

    target_dir = Path(folder).expanduser() if folder else DOWNLOADS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    response = requests.get(clean_url, stream=True, timeout=30, headers={"User-Agent": "STAR Assistant/1.0"})
    response.raise_for_status()

    filename = filename_from_response(clean_url, response)
    path = unique_path(target_dir / filename)

    with path.open("wb") as file:
        for chunk in response.iter_content(chunk_size=1024 * 128):
            if chunk:
                file.write(chunk)

    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "content_type": response.headers.get("content-type"),
    }


def filename_from_response(url, response):
    content_disposition = response.headers.get("content-disposition", "")
    match = re.search(r'filename="?([^";]+)"?', content_disposition)
    if match:
        return safe_filename(match.group(1))

    parsed_name = Path(urlparse(url).path).name
    if parsed_name:
        return safe_filename(parsed_name)

    content_type = response.headers.get("content-type", "").split(";")[0]
    extension = mimetypes.guess_extension(content_type) or ".download"
    return "download" + extension


def unique_path(path):
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def safe_filename(name):
    clean = re.sub(r'[<>:"/\\|?*]', "_", str(name).strip())
    return clean or "download"


def wait(seconds):
    time.sleep(max(0, float(seconds)))
