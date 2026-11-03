"""Run with:  .venv/bin/python -m unittest discover tests"""
import unittest
from datetime import datetime
from pathlib import Path

from canvas import TZ, format_week, in_window, parse_feed, week_window

NOW = datetime(2026, 10, 28, 9, 0, tzinfo=TZ)  # a Wednesday
DATA = (Path(__file__).parent / "sample.ics").read_bytes()


class WeekWindowTests(unittest.TestCase):
    def test_this_week_is_monday_to_monday(self):
        start, end = week_window(0, NOW)
        self.assertEqual((start.month, start.day, start.hour, start.weekday()), (10, 26, 0, 0))
        self.assertEqual((end.month, end.day, end.hour), (11, 2, 0))

    def test_sunday_belongs_to_the_week_before_it(self):
        start, _ = week_window(0, datetime(2026, 11, 1, 22, 0, tzinfo=TZ))
        self.assertEqual((start.month, start.day), (10, 26))

    def test_offset_survives_daylight_saving_change(self):
        # Clocks fall back on Sun Nov 1 2026. Next week must still start at local midnight.
        start, _ = week_window(1, NOW)
        self.assertEqual((start.month, start.day, start.hour, start.minute), (11, 2, 0, 0))

    def test_end_is_exclusive(self):
        start, end = week_window(0, NOW)
        items = parse_feed(DATA)
        self.assertTrue(all(start <= d.due < end for d in in_window(items, start, end)))


class FormatWeekTests(unittest.TestCase):
    def setUp(self):
        self.items = parse_feed(DATA)

    def test_this_week(self):
        text = format_week(self.items, 0, NOW)
        self.assertIn("This week", text)
        self.assertIn("Project 2", text)
        self.assertIn("Quiz 3", text)
        self.assertNotIn("Homework 4", text)

    def test_last_week_shows_past_work(self):
        text = format_week(self.items, -1, NOW)
        self.assertIn("Last week", text)
        self.assertIn("Homework 4", text)

    def test_calendar_events_are_left_out(self):
        text = format_week(self.items, 1, NOW)
        self.assertIn("Nothing due this week.", text)
        self.assertNotIn("Drop/Add", text)

    def test_far_weeks_are_named_by_date(self):
        self.assertIn("Week of Dec 14", format_week(self.items, 7, NOW))
