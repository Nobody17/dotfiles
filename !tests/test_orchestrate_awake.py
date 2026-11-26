"""Run with python3 -m unittest discover -s '!tests' -p 'test_orchestrate_awake.py'."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents/.agents/skills/orchestrate-tickets/scripts"))

import awake  # noqa: E402


class SleptSecondsTests(unittest.TestCase):
    def test_no_sleep_when_both_clocks_advance_together(self):
        self.assertEqual(0.0, awake.slept_seconds(1000.0, 1015.0, 50.0, 65.0))

    def test_sleep_is_the_wall_time_the_steady_clock_did_not_count(self):
        self.assertEqual(3600.0, awake.slept_seconds(1000.0, 4615.0, 50.0, 65.0))

    def test_a_short_difference_is_not_a_sleep(self):
        self.assertEqual(0.0, awake.slept_seconds(1000.0, 1045.0, 50.0, 65.0))

    def test_meter_reports_each_sleep_once(self):
        wall, steady = iter([0.0, 15.0, 7215.0, 7230.0]), iter([0.0, 15.0, 30.0, 45.0])
        meter = awake.SleepMeter(wall_clock=lambda: next(wall), steady_clock=lambda: next(steady))

        self.assertEqual([0.0, 7185.0, 0.0], [meter.take(), meter.take(), meter.take()])


if __name__ == "__main__":
    unittest.main()
