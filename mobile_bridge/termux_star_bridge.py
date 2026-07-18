#!/usr/bin/env python3
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request


BASE_URL = os.getenv("STAR_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SECRET = os.getenv("MOBILE_SHARED_SECRET", "")
DEVICE_ID = os.getenv("STAR_DEVICE_ID") or socket.gethostname() or "android_phone"
DEVICE_NAME = os.getenv("STAR_DEVICE_NAME") or DEVICE_ID
POLL_SECONDS = float(os.getenv("STAR_POLL_SECONDS", "2"))

CAPABILITIES = [
    "notify",
    "speak",
    "vibrate",
    "open_url",
    "share_text",
    "call_intent",
    "sms_intent",
    "battery",
    "toast",
    "torch",
    "clipboard_set",
    "clipboard_get",
    "location",
    "wifi_connection",
    "volume_status",
    "volume_set",
    "brightness",
    "media_key",
    "device_info",
    "find_phone",
]


def with_secret(params=None):
    final = dict(params or {})
    if SECRET:
        final["secret"] = SECRET
    return final


def request_json(method, path, params=None, timeout=20):
    query = urllib.parse.urlencode(with_secret(params), doseq=True)
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    data = b"" if method.upper() == "POST" else None
    request = urllib.request.Request(url, data=data, method=method.upper())
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def command_exists(command):
    return shutil.which(command) is not None


def run_command(args, timeout=20):
    if not command_exists(args[0]):
        return {"status": "skipped", "message": f"{args[0]} not installed"}
    completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return {
        "status": "done" if completed.returncode == 0 else "error",
        "code": completed.returncode,
        "stdout": completed.stdout[-500:],
        "stderr": completed.stderr[-500:],
    }


def run_steps(steps):
    results = []
    final_status = "done"
    for args in steps:
        result = run_command(args)
        results.append({"args": args, "result": result})
        if result.get("status") == "error":
            final_status = "error"
        elif result.get("status") == "skipped" and final_status != "error":
            final_status = "skipped"
    return {"status": final_status, "steps": results}


def safe_url(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if ":" not in text and "." in text:
        return "https://" + text
    return text


def execute_action(action):
    kind = action.get("action")
    payload = action.get("payload") or {}

    if kind == "notify":
        title = str(payload.get("title") or "STAR")
        body = str(payload.get("body") or "")
        return run_command(["termux-notification", "--title", title, "--content", body])

    if kind == "speak":
        text = str(payload.get("text") or "")
        return run_command(["termux-tts-speak", text])

    if kind == "vibrate":
        duration = str(int(payload.get("duration_ms") or 700))
        return run_command(["termux-vibrate", "-d", duration])

    if kind == "open_url":
        url = safe_url(payload.get("url"))
        if not url:
            return {"status": "error", "message": "missing url"}
        return run_command(["termux-open-url", url])

    if kind == "share_text":
        text = str(payload.get("text") or "")
        if not text:
            return {"status": "error", "message": "missing text"}
        return run_command(["termux-share", "-a", "send", text])

    if kind == "call_intent":
        number = urllib.parse.quote(str(payload.get("number") or ""))
        if not number:
            return {"status": "error", "message": "missing number"}
        return run_command(["termux-open-url", f"tel:{number}"])

    if kind == "sms_intent":
        number = urllib.parse.quote(str(payload.get("number") or ""))
        body = urllib.parse.quote(str(payload.get("body") or ""))
        if not number:
            return {"status": "error", "message": "missing number"}
        return run_command(["termux-open-url", f"sms:{number}?body={body}"])

    if kind == "battery":
        return run_command(["termux-battery-status"])

    if kind == "toast":
        text = str(payload.get("text") or "STAR")
        return run_command(["termux-toast", text])

    if kind == "torch":
        state = str(payload.get("state") or "on").lower()
        state = "on" if state in {"on", "true", "1", "yes"} else "off"
        return run_command(["termux-torch", state])

    if kind == "clipboard_set":
        text = str(payload.get("text") or "")
        if not text:
            return {"status": "error", "message": "missing text"}
        return run_command(["termux-clipboard-set", text])

    if kind == "clipboard_get":
        return run_command(["termux-clipboard-get"])

    if kind == "location":
        provider = str(payload.get("provider") or "network").lower()
        if provider not in {"gps", "network", "passive"}:
            provider = "network"
        return run_command(["termux-location", "-p", provider], timeout=45)

    if kind == "wifi_connection":
        return run_command(["termux-wifi-connectioninfo"])

    if kind == "volume_status":
        return run_command(["termux-volume"])

    if kind == "volume_set":
        stream = str(payload.get("stream") or "music").lower()
        level = str(int(payload.get("level") or 10))
        return run_command(["termux-volume", stream, level])

    if kind == "brightness":
        value = str(payload.get("value") or "auto").lower()
        if value != "auto":
            value = str(max(0, min(255, int(float(value)))))
        return run_command(["termux-brightness", value])

    if kind == "media_key":
        key = str(payload.get("key") or "play_pause").lower()
        keycodes = {
            "play_pause": "85",
            "play": "126",
            "pause": "127",
            "next": "87",
            "previous": "88",
            "prev": "88",
            "stop": "86",
        }
        keycode = keycodes.get(key, "85")
        return run_command(["input", "keyevent", keycode])

    if kind == "device_info":
        return run_command(["termux-telephony-deviceinfo"])

    if kind == "find_phone":
        message = str(payload.get("message") or "STAR found your phone.")
        return run_steps(
            [
                ["termux-volume", "music", str(int(payload.get("volume") or 15))],
                ["termux-vibrate", "-d", str(int(payload.get("duration_ms") or 1200))],
                ["termux-tts-speak", message],
                ["termux-toast", message],
            ]
        )

    return {"status": "skipped", "message": f"unknown action {kind}"}


def register():
    return request_json(
        "POST",
        "/mobile/devices/register",
        {
            "device_id": DEVICE_ID,
            "name": DEVICE_NAME,
            "platform": "termux_android",
            "capabilities": json.dumps(CAPABILITIES),
        },
    )


def complete(action_id, result):
    status = result.get("status") or "done"
    if status not in {"done", "error", "skipped"}:
        status = "done"
    return request_json(
        "POST",
        f"/mobile/actions/{action_id}/complete",
        {
            "device_id": DEVICE_ID,
            "status": status,
            "result": json.dumps(result),
        },
    )


def loop():
    print(f"STAR Termux bridge connecting to {BASE_URL}")
    registered = register()
    if not registered.get("authorized"):
        raise SystemExit(f"Registration failed: {registered}")
    print(f"Registered phone bridge as {DEVICE_ID}")

    while True:
        try:
            pulled = request_json("GET", "/mobile/actions/pull", {"device_id": DEVICE_ID, "limit": 5})
            if not pulled.get("authorized"):
                print("Pull failed:", pulled)
                time.sleep(POLL_SECONDS)
                continue
            for action in pulled.get("actions", []):
                print(f"Running action #{action['id']}: {action.get('action')}")
                result = execute_action(action)
                complete(action["id"], result)
        except KeyboardInterrupt:
            print("Stopping STAR Termux bridge.")
            return
        except Exception as exc:
            print("Bridge error:", exc, file=sys.stderr)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    loop()
