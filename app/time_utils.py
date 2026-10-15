from datetime import datetime, timezone, timedelta
from typing import Optional, Union

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    # Robust fallback for environments without tzdata
    IST = timezone(timedelta(hours=5, minutes=30), name="IST")

def ist_now() -> datetime:
    """Returns the current timezone-aware datetime in India Standard Time (IST)."""
    return datetime.now(IST)

def ist_today_date():
    """Returns today's date in IST."""
    return ist_now().date()

def ist_today_str() -> str:
    """Returns today's date as YYYY-MM-DD in IST."""
    return ist_now().strftime("%Y-%m-%d")

def ist_now_str() -> str:
    """Returns current timestamp as YYYY-MM-DD HH:MM:SS in IST."""
    return ist_now().strftime("%Y-%m-%d %H:%M:%S")

def parse_ist_datetime(dt_val: Union[str, datetime]) -> datetime:
    """Safely parse a string or datetime into an IST-aware datetime."""
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=IST)
        return dt_val.astimezone(IST)

    clean_str = dt_val.strip()
    # Strip any ISO T or Z or offset for parsing
    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d"
    ]:
        try:
            naive = datetime.strptime(clean_str.split("+")[0].split(".")[0], fmt)
            return naive.replace(tzinfo=IST)
        except ValueError:
            continue

    # Default fallback
    return ist_now()

def to_iso_ist_string(dt_val: Union[str, datetime]) -> str:
    """
    Format a datetime as standard ISO 8601 with +05:30 offset
    e.g. '2026-10-01T17:00:00+05:30' for clean browser JavaScript parsing.
    """
    dt = parse_ist_datetime(dt_val)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+05:30")

def format_time_12h(time_str: str) -> str:
    """Converts '19:30' or '19:30:00' to '07:30 PM'."""
    if not time_str:
        return ""
    clean = time_str.strip()
    if ":" not in clean:
        return clean
    parts = clean.split(":")
    hours = int(parts[0])
    minutes = int(parts[1]) if len(parts) > 1 else 0
    period = "PM" if hours >= 12 else "AM"
    h12 = hours % 12
    if h12 == 0:
        h12 = 12
    return f"{h12:02d}:{minutes:02d} {period}"

def format_deadline_display(deadline_val: Union[str, datetime]) -> str:
    """Formats deadline for user display in IST (e.g. '05:00 PM IST')."""
    dt = parse_ist_datetime(deadline_val)
    return dt.strftime("%I:%M %p")
