import datetime
import re

import star_productivity
import star_storage as storage


DEFAULT_DURATION_MINUTES = 60


def now():
    return datetime.datetime.now().replace(microsecond=0)


def iso(dt):
    return dt.replace(microsecond=0).isoformat() if dt else None


def parse_datetime(text):
    return star_productivity.parse_due_time(text)


def parse_duration_minutes(text, default=DEFAULT_DURATION_MINUTES):
    raw = str(text).lower()
    match = re.search(r"\bfor\s+(\d+)\s+(minute|minutes|min|hour|hours)\b", raw)
    if not match:
        return default

    amount = int(match.group(1))
    unit = match.group(2)
    if unit.startswith("hour"):
        amount *= 60
    return max(5, min(amount, 24 * 60))


def strip_event_phrases(text):
    cleaned = re.sub(r"\bfor\s+\d+\s+(minute|minutes|min|hour|hours)\b", "", text, flags=re.IGNORECASE)
    cleaned = star_productivity.strip_due_phrase(cleaned)
    return " ".join(cleaned.split()).strip(" .")


def parse_location(text):
    raw = str(text)
    lower = raw.lower()
    for marker in [" at location ", " in location ", " location "]:
        if marker in lower:
            index = lower.index(marker)
            before = raw[:index].strip()
            after = raw[index + len(marker):].strip()
            return before, after
    return raw, None


def add_event(title, starts_at, ends_at=None, location=None, notes=None):
    clean_title = str(title).strip()
    if not clean_title or not starts_at:
        return None

    current = storage.utc_now()
    with storage.connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO calendar_events(title, starts_at, ends_at, location, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (clean_title, iso(starts_at), iso(ends_at), location, notes, current, current),
        )

    storage.add_log("info", "calendar_event_created", {"id": cur.lastrowid, "starts_at": iso(starts_at)})
    return cur.lastrowid


def create_event_from_text(payload):
    starts_at = parse_datetime(payload)
    if not starts_at:
        return {"error": "Tell me when, like today at 5 pm, tomorrow at 9 am, or in 2 hours."}

    duration = parse_duration_minutes(payload)
    ends_at = starts_at + datetime.timedelta(minutes=duration)
    title_text = strip_event_phrases(payload)
    title_text, location = parse_location(title_text)
    if not title_text:
        return {"error": "Tell me the event title."}

    event_id = add_event(title_text, starts_at, ends_at=ends_at, location=location)
    return {"id": event_id, "starts_at": starts_at, "ends_at": ends_at, "title": title_text, "location": location}


def list_events(limit=20, status="scheduled"):
    with storage.connect() as conn:
        if status == "all":
            rows = conn.execute(
                "SELECT * FROM calendar_events ORDER BY starts_at ASC LIMIT ?",
                (int(limit),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM calendar_events WHERE status = ? ORDER BY starts_at ASC LIMIT ?",
                (status, int(limit)),
            ).fetchall()
    return [storage.row_to_dict(row) for row in rows]


def events_between(start, end, status="scheduled", limit=50):
    with storage.connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM calendar_events
            WHERE status = ? AND starts_at >= ? AND starts_at < ?
            ORDER BY starts_at ASC LIMIT ?
            """,
            (status, iso(start), iso(end), int(limit)),
        ).fetchall()
    return [storage.row_to_dict(row) for row in rows]


def upcoming_events(limit=10):
    current = iso(now())
    with storage.connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM calendar_events
            WHERE status = 'scheduled' AND starts_at >= ?
            ORDER BY starts_at ASC LIMIT ?
            """,
            (current, int(limit)),
        ).fetchall()
    return [storage.row_to_dict(row) for row in rows]


def agenda(day="today"):
    base = now()
    if day == "tomorrow":
        base = base + datetime.timedelta(days=1)
    start = base.replace(hour=0, minute=0, second=0)
    end = start + datetime.timedelta(days=1)
    return events_between(start, end)


def delete_event(event_id):
    with storage.connect() as conn:
        cur = conn.execute("DELETE FROM calendar_events WHERE id = ?", (int(event_id),))
    deleted = cur.rowcount > 0
    if deleted:
        storage.add_log("info", "calendar_event_deleted", {"id": int(event_id)})
    return deleted


def cancel_event(event_id):
    with storage.connect() as conn:
        cur = conn.execute(
            "UPDATE calendar_events SET status = 'cancelled', updated_at = ? WHERE id = ? AND status != 'cancelled'",
            (storage.utc_now(), int(event_id)),
        )
    cancelled = cur.rowcount > 0
    if cancelled:
        storage.add_log("info", "calendar_event_cancelled", {"id": int(event_id)})
    return cancelled


def format_time_range(event):
    start = event.get("starts_at", "")
    end = event.get("ends_at")
    if not end:
        return start
    return f"{start} to {end[11:16]}"


def format_events(events, empty="No calendar events found."):
    if not events:
        return empty

    parts = []
    for event in events[:8]:
        location = f" at {event['location']}" if event.get("location") else ""
        parts.append(f"{event['id']}: {event['title']} on {format_time_range(event)}{location}")
    return "Calendar: " + ", ".join(parts) + "."
