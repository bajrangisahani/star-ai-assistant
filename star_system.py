import os
import platform
import shutil
import socket
import subprocess
import time
from pathlib import Path

import psutil
import pyautogui


def bytes_to_gb(value):
    return round(value / (1024 ** 3), 2)


def percent(value):
    return round(float(value), 1)


def get_cpu_info():
    return {
        "usage_percent": percent(psutil.cpu_percent(interval=0.2)),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
    }


def get_memory_info():
    memory = psutil.virtual_memory()
    return {
        "total_gb": bytes_to_gb(memory.total),
        "used_gb": bytes_to_gb(memory.used),
        "available_gb": bytes_to_gb(memory.available),
        "usage_percent": percent(memory.percent),
    }


def get_disk_info(path=None):
    target = path or str(Path.home().anchor or "C:\\")
    usage = shutil.disk_usage(target)
    return {
        "path": target,
        "total_gb": bytes_to_gb(usage.total),
        "used_gb": bytes_to_gb(usage.used),
        "free_gb": bytes_to_gb(usage.free),
        "usage_percent": percent((usage.used / usage.total) * 100),
    }


def get_battery_info():
    battery = psutil.sensors_battery()
    if battery is None:
        return {"available": False}

    return {
        "available": True,
        "percent": percent(battery.percent),
        "plugged_in": bool(battery.power_plugged),
        "seconds_left": battery.secsleft,
    }


def get_network_info():
    counters = psutil.net_io_counters()
    return {
        "hostname": socket.gethostname(),
        "bytes_sent_mb": round(counters.bytes_sent / (1024 ** 2), 2),
        "bytes_recv_mb": round(counters.bytes_recv / (1024 ** 2), 2),
        "interfaces": sorted(psutil.net_if_addrs().keys()),
    }


def get_windows_info():
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER"),
    }


def get_system_status():
    return {
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "disk": get_disk_info(),
        "battery": get_battery_info(),
        "network": get_network_info(),
        "windows": get_windows_info(),
    }


def list_processes(limit=25):
    processes = []
    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            processes.append(
                {
                    "pid": info.get("pid"),
                    "name": info.get("name"),
                    "username": info.get("username"),
                    "cpu_percent": percent(info.get("cpu_percent") or 0),
                    "memory_percent": percent(info.get("memory_percent") or 0),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(key=lambda item: item["memory_percent"], reverse=True)
    return processes[: int(limit)]


def list_installed_apps(app_database, limit=100):
    names = sorted(app_database.keys())
    return [{"name": name, "shortcut": app_database[name]} for name in names[: int(limit)]]


def format_system_summary(status):
    cpu = status["cpu"]
    memory = status["memory"]
    disk = status["disk"]
    battery = status["battery"]

    parts = [
        f"CPU is at {cpu['usage_percent']} percent",
        f"RAM is at {memory['usage_percent']} percent",
        f"disk is at {disk['usage_percent']} percent with {disk['free_gb']} GB free",
    ]

    if battery.get("available"):
        state = "charging" if battery["plugged_in"] else "on battery"
        parts.append(f"battery is {battery['percent']} percent and {state}")

    return ", ".join(parts) + "."


def control_volume(command):
    text = command.lower()

    if "mute" in text:
        pyautogui.press("volumemute")
        return "Volume muted."

    if any(word in text for word in ["up", "increase", "raise"]):
        pyautogui.press("volumeup", presses=5)
        return "Volume increased."

    if any(word in text for word in ["down", "decrease", "lower", "reduce"]):
        pyautogui.press("volumedown", presses=5)
        return "Volume decreased."

    return None


def control_brightness(command):
    text = command.lower()

    if not platform.system().lower().startswith("windows"):
        return "Brightness control is only configured for Windows right now."

    if any(word in text for word in ["up", "increase", "raise"]):
        delta = 10
    elif any(word in text for word in ["down", "decrease", "lower", "reduce"]):
        delta = -10
    else:
        return "Tell me whether to increase or decrease brightness."

    script = (
        "$m=(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness;"
        f"$n=[Math]::Max(0,[Math]::Min(100,$m+({delta})));"
        "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,$n)"
    )

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        return "Brightness control failed on this device."

    return "Brightness updated."


def lock_pc():
    subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
    return "Locking PC."


def sleep_pc():
    subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
    return "Putting PC to sleep."


def shutdown_pc():
    subprocess.Popen(["shutdown", "/s", "/t", "5"])
    return "Shutting down in 5 seconds."


def restart_pc():
    subprocess.Popen(["shutdown", "/r", "/t", "5"])
    return "Restarting in 5 seconds."


def cancel_power_action():
    result = subprocess.run(["shutdown", "/a"], capture_output=True, text=True)
    if result.returncode == 0:
        return "Pending shutdown or restart cancelled."
    return "No pending shutdown or restart was found."


def uptime_seconds():
    return int(time.time() - psutil.boot_time())
