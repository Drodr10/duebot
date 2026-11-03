"""Run with:  .venv/bin/python -m unittest discover tests"""
import unittest
from datetime import datetime
from pathlib import Path

from canvas import LIMIT, TZ, clip, format_digest, parse_feed, upcoming

NOW = datetime(2026, 10, 28, 9, 0, tzinfo=TZ)
DATA = (Path(__file__).parent / "sample.ics").read_bytes()


class CanvasFeedTests(unittest.TestCase):
    def test_parses_every_event(self):
        self.assertEqual(len(parse_feed(DATA)), 5)

    def test_course_code_and_title_split(self):
        quiz = next(d for d in parse_feed(DATA) if d.title.startswith("Quiz 3"))
        self.assertEqual(quiz.course, "COP4020")
        self.assertEqual(quiz.title, "Quiz 3: Parsing and Syntax")
        self.assertFalse(quiz.all_day)

    def test_utc_converted_to_local(self):
        proj = next(d for d in parse_feed(DATA) if d.title.startswith("Project 2"))
        # 03:59:59Z on Oct 30 is 11:59 PM Oct 29 in Gainesville (EDT)
        self.assertEqual((proj.due.month, proj.due.day, proj.due.hour, proj.due.minute), (10, 29, 23, 59))

    def test_all_day_calendar_event(self):
        ev = next(d for d in parse_feed(DATA) if d.title == "Drop/Add Deadline")
        self.assertTrue(ev.all_day)
        self.assertEqual(ev.course, "")
        self.assertEqual(ev.kind, "event")

    def test_uid_kept(self):
        quiz = next(d for d in parse_feed(DATA) if d.title.startswith("Quiz 3"))
        self.assertEqual(quiz.uid, "event-assignment-1002")

    def test_kind_from_uid(self):
        kinds = {d.title: d.kind for d in parse_feed(DATA)}
        self.assertEqual(kinds["Quiz 3: Parsing and Syntax"], "assignment")
        self.assertEqual(kinds["Drop/Add Deadline"], "event")

    def test_upcoming_can_include_events(self):
        titles = [d.title for d in upcoming(parse_feed(DATA), days=7, now=NOW, kind=None)]
        self.assertIn("Drop/Add Deadline", titles)

    def test_upcoming_filters_past_and_far_future(self):
        titles = [d.title for d in upcoming(parse_feed(DATA), days=7, now=NOW)]
        self.assertEqual(titles, ["Project 2: Hash Tables", "Quiz 3: Parsing and Syntax"])  # lecture-type events excluded

    def test_digest_text(self):
        text = format_digest(upcoming(parse_feed(DATA), 7, NOW), 7, NOW)
        self.assertIn("**Tomorrow**", text)
        self.assertIn("`COP3530` [Project 2: Hash Tables]", text)
        self.assertNotIn("Drop/Add", text)
        self.assertNotIn("Homework 4", text)

    def test_empty(self):
        self.assertIn("Nothing due", format_digest([], 7, NOW))


if __name__ == "__main__":
    unittest.main()


class ClipTests(unittest.TestCase):
    """Discord rejects messages over 2000 characters; a busy month of deadlines gets there."""

    def test_short_text_untouched(self):
        self.assertEqual(clip("hi"), "hi")

    def test_long_text_cut_on_a_line(self):
        out = clip("\n".join(f"• line {i}" for i in range(500)))
        self.assertLessEqual(len(out), LIMIT)
        self.assertTrue(out.endswith("…and more"))

    def test_no_empty_day_heading_left_behind(self):
        text = "\n".join(f"**Day {i}**\n• thing {i}" for i in range(400))
        self.assertTrue(clip(text).splitlines()[-2].startswith("• "))
