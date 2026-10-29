"""
reminders.py — "tell me 24 hours before it's due", done properly.

The logic is easy. The hard part is NOT telling you twice: the bot has to remember
what it already sent, and that memory has to survive a restart (and a container
restart), or you get every reminder again each time it boots. So the sent-list
lives in a small JSON file. In Docker, mount a volume on its folder (see README).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from canvas import TZ, Deadline


def parse_leads(spec: str) -> list[float]:
    """'24,1' -> [24.0, 1.0] hours. Blank -> [] (reminders off)."""
    return [float(x) for x in spec.replace(";", ",").split(",") if x.strip()]


def due_reminders(items: list[Deadline], leads: list[float], now: datetime, sent: set[str]) -> list[tuple[Deadline, float]]:
    """Which (deadline, lead-hours) pairs should fire right now?
    A pair fires once we are inside its window (due - lead <= now < due) and it hasn't been sent."""
    out = []
    for d in items:
        if d.kind != "assignment" or d.due <= now:
            continue
        for lead in leads:
            if d.due - timedelta(hours=lead) <= now and key(d, lead) not in sent:
                out.append((d, lead))
    return sorted(out, key=lambda pair: pair[0].due)


def key(d: Deadline, lead: float) -> str:
    return f"{d.uid}@{lead:g}h"


def describe(d: Deadline, lead: float) -> str:
    when = "all day" if d.all_day else d.due.strftime("%-I:%M %p")
    day = d.due.strftime("%a %b %-d")
    course = f"`{d.course}` " if d.course else ""
    title = f"[{d.title}]({d.url})" if d.url else d.title
    return f"⏰ **Due {lead_text(lead)}:** {course}{title} — {day}, {when}"


def lead_text(lead: float) -> str:
    if lead < 1:
        return f"in {int(round(lead * 60))} minutes"
    if lead < 24:
        return f"in {lead:g} hour" + ("" if lead == 1 else "s")
    days = lead / 24
    return f"in {days:g} day" + ("" if days == 1 else "s")


# ------------------------------------------------------------ persistence ----
def load_sent(path: Path) -> set[str]:
    try:
        return set(json.loads(path.read_text()))
    except (FileNotFoundError, ValueError):
        return set()


def save_sent(path: Path, sent: set[str], items: list[Deadline], now: datetime | None = None) -> None:
    """Write the sent-list, dropping entries for deadlines that have passed so the file stays tiny."""
    now = now or datetime.now(TZ)
    live = {d.uid for d in items if d.due > now}
    keep = sorted(k for k in sent if k.split("@")[0] in live)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(keep, indent=0))
    sent.intersection_update(keep)
