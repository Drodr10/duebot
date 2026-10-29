import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from canvas import TZ, parse_feed
from reminders import describe, due_reminders, key, lead_text, load_sent, parse_leads, save_sent

DATA = (Path(__file__).parent / "sample.ics").read_bytes()
ITEMS = parse_feed(DATA)
# Project 2 is due Oct 29 11:59 PM, Quiz 3 is due Oct 30 11:59 PM (local).


class ReminderTests(unittest.TestCase):
    def test_parse_leads(self):
        self.assertEqual(parse_leads("24,1"), [24.0, 1.0])
        self.assertEqual(parse_leads(""), [])
        self.assertEqual(parse_leads("0.5; 48"), [0.5, 48.0])

    def test_fires_inside_window_only(self):
        now = datetime(2026, 10, 29, 9, 0, tzinfo=TZ)           # 15h before Project 2, 39h before Quiz 3
        fire = due_reminders(ITEMS, [24, 1], now, set())
        self.assertEqual([(d.title, lead) for d, lead in fire], [("Project 2: Hash Tables", 24)])

    def test_one_hour_window_later(self):
        now = datetime(2026, 10, 29, 23, 30, tzinfo=TZ)         # 29 min before Project 2
        fire = due_reminders(ITEMS, [24, 1], now, set())
        self.assertEqual({lead for _, lead in fire if _.title.startswith("Project 2")}, {24, 1})

    def test_never_twice(self):
        now = datetime(2026, 10, 29, 9, 0, tzinfo=TZ)
        sent = {key(next(d for d in ITEMS if d.title.startswith("Project 2")), 24)}
        self.assertEqual(due_reminders(ITEMS, [24], now, sent), [])

    def test_skips_lectures_and_past(self):
        now = datetime(2026, 11, 3, 9, 0, tzinfo=TZ)            # Drop/Add (event) is today; everything earlier is past
        self.assertEqual(due_reminders(ITEMS, [24], now, set()), [])

    def test_persistence_roundtrip_and_pruning(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "sent.json"
            proj = next(d for d in ITEMS if d.title.startswith("Project 2"))
            hw = next(d for d in ITEMS if d.title.startswith("Homework 4"))   # already past
            sent = {key(proj, 24), key(hw, 24)}
            save_sent(path, sent, ITEMS, now=datetime(2026, 10, 28, 9, 0, tzinfo=TZ))
            self.assertEqual(load_sent(path), {key(proj, 24)})               # Homework 4 pruned
            self.assertEqual(load_sent(Path(tmp) / "missing.json"), set())

    def test_text(self):
        self.assertEqual(lead_text(1), "in 1 hour")
        self.assertEqual(lead_text(24), "in 1 day")
        self.assertEqual(lead_text(48), "in 2 days")
        self.assertEqual(lead_text(0.5), "in 30 minutes")
        proj = next(d for d in ITEMS if d.title.startswith("Project 2"))
        self.assertIn("Due in 1 day:", describe(proj, 24))
        self.assertIn("`COP3530`", describe(proj, 24))


if __name__ == "__main__":
    unittest.main()
