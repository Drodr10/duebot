"""
canvas.py — talk to Canvas.

Canvas has no student-friendly API at UF, but every account has a private
*calendar feed*: an .ics file with every assignment, quiz and event that has a
due date. We download it over plain HTTPS and parse it. No token, no OAuth.

Find yours: Canvas -> Calendar -> "Calendar Feed" (bottom of the right sidebar).
Treat the URL like a password: anyone holding it can read your calendar.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo

import aiohttp
from icalendar import Calendar

TZ = ZoneInfo("America/New_York")  # Gainesville


@dataclass
class Deadline:
    title: str          # "Quiz 3: Parsing and Syntax"
    course: str         # "COP4020"  (Canvas puts it in [brackets] at the end of SUMMARY)
    due: datetime       # timezone-aware, converted to TZ
    url: str            # link straight to the assignment
    all_day: bool       # calendar events without a time (DTSTART;VALUE=DATE:...)


async def fetch_feed(url: str) -> bytes:
    """Download the raw .ics bytes. This is the 'call an external API' moment."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            return await resp.read()


_COURSE_RE = re.compile(r"^(?P<title>.*?)\s*\[(?P<course>[^\]]+)\]\s*$")


def parse_feed(data: bytes) -> list[Deadline]:
    """Turn .ics bytes into a list of Deadline objects. Ignores anything without a date."""
    cal = Calendar.from_ical(data)
    items: list[Deadline] = []
    for ev in cal.walk("VEVENT"):
        summary = str(ev.get("SUMMARY", "")).strip()
        start = ev.get("DTSTART")
        if not summary or start is None:
            continue

        m = _COURSE_RE.match(summary)
        title, course = (m["title"], m["course"]) if m else (summary, "")

        dt = start.dt
        if isinstance(dt, datetime):
            # Canvas sends UTC ("...Z"). Make it local.
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            due, all_day = dt.astimezone(TZ), False
        else:
            # Date-only entries have no time, so treat them as "end of that day".
            due, all_day = datetime.combine(dt, time(23, 59), tzinfo=TZ), True

        items.append(Deadline(title, course, due, str(ev.get("URL", "")), all_day))
    return items


def upcoming(items: list[Deadline], days: int = 7, now: datetime | None = None) -> list[Deadline]:
    """Everything due from now until `days` from now, soonest first."""
    now = now or datetime.now(TZ)
    horizon = now + timedelta(days=days)
    return sorted((d for d in items if now <= d.due <= horizon), key=lambda d: d.due)


def format_digest(items: list[Deadline], days: int = 7, now: datetime | None = None) -> str:
    """Markdown for Discord: grouped by day, one line per deadline."""
    now = now or datetime.now(TZ)
    if not items:
        return f"Nothing due in the next {days} days. Go outside."

    lines: list[str] = []
    current: date | None = None
    for d in items:
        day = d.due.date()
        if day != current:
            current = day
            label = {0: "Today", 1: "Tomorrow"}.get((day - now.date()).days, d.due.strftime("%A %b %-d"))
            lines.append(f"\n**{label}**")
        when = "all day" if d.all_day else d.due.strftime("%-I:%M %p")
        course = f"`{d.course}` " if d.course else ""
        title = f"[{d.title}]({d.url})" if d.url else d.title
        lines.append(f"• {when} — {course}{title}")
    return "\n".join(lines).strip()


async def get_digest(url: str, days: int = 7) -> str:
    """The one call bot.py actually needs: feed URL in, Discord-ready text out."""
    items = parse_feed(await fetch_feed(url))
    return format_digest(upcoming(items, days), days)


if __name__ == "__main__":
    # Try your own feed without Discord:  python canvas.py "https://ufl.instructure.com/feeds/calendars/user_....ics"
    # or a saved file:                     python canvas.py tests/sample.ics
    import asyncio

    src = sys.argv[1] if len(sys.argv) > 1 else "tests/sample.ics"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7

    async def main() -> None:
        data = await fetch_feed(src) if src.startswith("http") else open(src, "rb").read()
        print(format_digest(upcoming(parse_feed(data), days), days))

    asyncio.run(main())
