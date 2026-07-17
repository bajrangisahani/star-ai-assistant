import datetime
import re

import star_storage as storage


POMODORO = {
    "active": False,
    "started_at": None,
    "ends_at": None,
    "minutes": 25,
    "label": "focus",
}


def now():
    return datetime.datetime.now().replace(microsecond=0)


def iso(dt):
    return dt.replace(microsecond=0).isoformat()


def parse_due_time(text):
    raw = text.lower().strip()
    current = now()

    match = re.search(r"\bin\s+(\d+)\s+(minute|minutes|min|hour|hours|day|days)\b", raw)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit.startswith("min"):
            return current + datetime.timedelta(minutes=amount)
        if unit.startswith("hour"):
            return current + datetime.timedelta(hours=amount)
        return current + datetime.timedelta(days=amount)

    base = current
    if "tomorrow" in raw:
        base = current + datetime.timedelta(days=1)

    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", raw)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        suffix = time_match.group(3)

        if suffix == "pm" and hour != 12:
            hour += 12
        elif suffix == "am" and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            due = base.replace(hour=hour, minute=minute, second=0)
            if "tomorrow" not in raw and due < current:
                due += datetime.timedelta(days=1)
            return due

    if "today" in raw:
        return current.replace(hour=20, minute=0, second=0)

    if "tomorrow" in raw:
        return base.replace(hour=9, minute=0, second=0)

    return None


def strip_due_phrase(text):
    cleaned = re.sub(r"\bin\s+\d+\s+(minute|minutes|min|hour|hours|day|days)\b", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(today|tomorrow)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bat\s+\d{1,2}(?::\d{2})?\s*(am|pm)?\b", "", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split()).strip()


def add_note(content, title=None, category="general"):
    clean_content = str(content).strip()
    if not clean_content:
        return None

    current = storage.utc_now()
    with storage.connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO notes(title, content, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, clean_content, category, current, current),
        )

    storage.add_log("info", "note_created", {"id": cur.lastrowid, "category": category})
    return cur.lastrowid


def list_notes(limit=20, query=None):
    with storage.connect() as conn:
        if query:
            pattern = f"%{query.lower().strip()}%"
            rows = conn.execute(
                """
                SELECT * FROM notes
                WHERE lower(content) LIKE ? OR lower(title) LIKE ? OR lower(category) LIKE ?
                ORDER BY id DESC LIMIT ?
                """,
                (pattern, pattern, pattern, int(limit)),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM notes ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
    return [storage.row_to_dict(row) for row in rows]


def delete_note(note_id):
    with storage.connect() as conn:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (int(note_id),))
    deleted = cur.rowcount > 0
    if deleted:
        storage.add_log("info", "note_deleted", {"id": int(note_id)})
    return deleted


def add_task(title, priority="normal", due_at=None):
    clean_title = str(title).strip()
    if not clean_title:
        return None

    with storage.connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks(title, priority, due_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (clean_title, priority, iso(due_at) if due_at else None, storage.utc_now()),
        )

    storage.add_log("info", "task_created", {"id": cur.lastrowid, "priority": priority})
    return cur.lastrowid


def list_tasks(status="open", limit=20):
    with storage.connect() as conn:
        if status == "all":
            rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, int(limit)),
            ).fetchall()
    return [storage.row_to_dict(row) for row in rows]


def complete_task(task_id):
    with storage.connect() as conn:
        cur = conn.execute(
            "UPDATE tasks SET status = 'done', completed_at = ? WHERE id = ? AND status != 'done'",
            (storage.utc_now(), int(task_id)),
        )
    done = cur.rowcount > 0
    if done:
        storage.add_log("info", "task_completed", {"id": int(task_id)})
    return done


def delete_task(task_id):
    with storage.connect() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (int(task_id),))
    deleted = cur.rowcount > 0
    if deleted:
        storage.add_log("info", "task_deleted", {"id": int(task_id)})
    return deleted


def add_reminder(text, due_at):
    clean_text = str(text).strip()
    if not clean_text or not due_at:
        return None

    with storage.connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO reminders(text, due_at, created_at)
            VALUES (?, ?, ?)
            """,
            (clean_text, iso(due_at), storage.utc_now()),
        )

    storage.add_log("info", "reminder_created", {"id": cur.lastrowid, "due_at": iso(due_at)})
    return cur.lastrowid


def list_reminders(status="open", limit=20):
    with storage.connect() as conn:
        if status == "all":
            rows = conn.execute("SELECT * FROM reminders ORDER BY due_at ASC LIMIT ?", (int(limit),)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE status = ? ORDER BY due_at ASC LIMIT ?",
                (status, int(limit)),
            ).fetchall()
    return [storage.row_to_dict(row) for row in rows]


def due_reminders(limit=20):
    current = iso(now())
    with storage.connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM reminders
            WHERE status = 'open' AND due_at <= ?
            ORDER BY due_at ASC LIMIT ?
            """,
            (current, int(limit)),
        ).fetchall()
    return [storage.row_to_dict(row) for row in rows]


def complete_reminder(reminder_id):
    with storage.connect() as conn:
        cur = conn.execute(
            "UPDATE reminders SET status = 'done', completed_at = ? WHERE id = ? AND status != 'done'",
            (storage.utc_now(), int(reminder_id)),
        )
    done = cur.rowcount > 0
    if done:
        storage.add_log("info", "reminder_completed", {"id": int(reminder_id)})
    return done


def delete_reminder(reminder_id):
    with storage.connect() as conn:
        cur = conn.execute("DELETE FROM reminders WHERE id = ?", (int(reminder_id),))
    deleted = cur.rowcount > 0
    if deleted:
        storage.add_log("info", "reminder_deleted", {"id": int(reminder_id)})
    return deleted


def start_pomodoro(minutes=25, label="focus"):
    current = now()
    duration = max(1, min(int(minutes), 180))
    POMODORO.update(
        {
            "active": True,
            "started_at": iso(current),
            "ends_at": iso(current + datetime.timedelta(minutes=duration)),
            "minutes": duration,
            "label": label,
        }
    )
    storage.add_log("info", "pomodoro_started", {"minutes": duration, "label": label})
    return POMODORO.copy()


def stop_pomodoro():
    was_active = POMODORO["active"]
    POMODORO.update({"active": False, "started_at": None, "ends_at": None})
    if was_active:
        storage.add_log("info", "pomodoro_stopped")
    return was_active


def pomodoro_status():
    state = POMODORO.copy()
    if not state["active"]:
        state["remaining_seconds"] = 0
        return state

    end = datetime.datetime.fromisoformat(state["ends_at"])
    remaining = max(0, int((end - now()).total_seconds()))
    state["remaining_seconds"] = remaining
    if remaining == 0:
        POMODORO["active"] = False
        state["active"] = False
    return state


def format_tasks(tasks):
    if not tasks:
        return "No open tasks."
    return "Tasks: " + ", ".join(f"{task['id']}: {task['title']}" for task in tasks[:8]) + "."


def format_notes(notes):
    if not notes:
        return "No notes found."
    return "Notes: " + ", ".join(f"{note['id']}: {note['content'][:60]}" for note in notes[:5]) + "."


def format_reminders(reminders):
    if not reminders:
        return "No open reminders."
    return "Reminders: " + ", ".join(f"{item['id']}: {item['text']} at {item['due_at']}" for item in reminders[:6]) + "."


def daily_briefing(system_summary):
    tasks = list_tasks(limit=5)
    reminders = list_reminders(limit=5)
    due = due_reminders(limit=5)

    parts = [system_summary]
    if tasks:
        parts.append(f"You have {len(tasks)} open task(s).")
    if reminders:
        parts.append(f"You have {len(reminders)} upcoming reminder(s).")
    if due:
        parts.append(f"{len(due)} reminder(s) are due now.")

    if len(parts) == 1:
        parts.append("No tasks or reminders are waiting.")

    return " ".join(parts)
