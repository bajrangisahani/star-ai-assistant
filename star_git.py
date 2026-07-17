import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def run_git(args, timeout=20):
    command = ["git", *args]
    try:
        result = subprocess.run(
            command,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": "git is not installed or not on PATH.", "returncode": 127}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "git command timed out.", "returncode": 124}

    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "returncode": result.returncode,
    }


def is_repo():
    result = run_git(["rev-parse", "--is-inside-work-tree"])
    return result["ok"] and result["stdout"].lower() == "true"


def status():
    if not is_repo():
        return {"ok": False, "message": "This folder is not a valid git repository."}
    result = run_git(["status", "--short"])
    return {"ok": result["ok"], "status": result["stdout"], "error": result["stderr"]}


def log(limit=5):
    if not is_repo():
        return {"ok": False, "message": "This folder is not a valid git repository."}
    result = run_git(["log", f"-{int(limit)}", "--oneline"])
    return {"ok": result["ok"], "log": result["stdout"], "error": result["stderr"]}


def diff(path=None):
    if not is_repo():
        return {"ok": False, "message": "This folder is not a valid git repository."}
    args = ["diff", "--"]
    if path:
        args.append(path)
    result = run_git(args, timeout=30)
    return {"ok": result["ok"], "diff": result["stdout"], "error": result["stderr"]}


def branch():
    if not is_repo():
        return {"ok": False, "message": "This folder is not a valid git repository."}
    result = run_git(["branch", "--show-current"])
    return {"ok": result["ok"], "branch": result["stdout"], "error": result["stderr"]}


def remotes():
    if not is_repo():
        return {"ok": False, "message": "This folder is not a valid git repository."}
    result = run_git(["remote", "-v"])
    return {"ok": result["ok"], "remotes": result["stdout"], "error": result["stderr"]}


def add_all():
    return run_git(["add", "."])


def commit(message):
    return run_git(["commit", "-m", message], timeout=60)


def pull():
    return run_git(["pull"], timeout=120)


def push():
    return run_git(["push"], timeout=120)


def format_status(result):
    if not result.get("ok"):
        return result.get("message") or result.get("error") or "Git status failed."
    return result.get("status") or "Working tree is clean."


def format_log(result):
    if not result.get("ok"):
        return result.get("message") or result.get("error") or "Git log failed."
    return result.get("log") or "No commits found."
