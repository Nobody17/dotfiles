"""Tests for orchestrate-tickets/scripts/launch-agent.py."""

import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "agents/.agents/skills/orchestrate-tickets/scripts/launch-agent.py"
SPECIFICATION = importlib.util.spec_from_file_location("launch_agent", SCRIPT)
launch_agent = importlib.util.module_from_spec(SPECIFICATION)
SPECIFICATION.loader.exec_module(launch_agent)


def agent_with(session_value):
    agent = {"name": "ns-t10", "agent_status": "idle", "cwd": "/work"}
    if session_value:
        agent["agent_session"] = {"value": session_value}
    return agent


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class WaitForSessionTests(unittest.TestCase):
    def test_returns_the_started_agent_when_it_has_a_session(self):
        clock = FakeClock()
        started = agent_with("abc")

        agent = launch_agent.wait_for_session(started, lambda: self.fail("no fetch needed"),
                                              timeout_seconds=30, sleep=clock.sleep, clock=clock.time)

        self.assertEqual(agent, started)

    def test_fetches_the_agent_again_until_herdr_knows_the_session(self):
        clock = FakeClock()
        answers = iter([agent_with(None), agent_with("5ef4")])

        agent = launch_agent.wait_for_session(agent_with(None), lambda: next(answers),
                                              timeout_seconds=30, sleep=clock.sleep, clock=clock.time)

        self.assertEqual(agent["agent_session"]["value"], "5ef4")
        self.assertEqual(clock.now, 2)

    def test_gives_up_after_the_timeout(self):
        clock = FakeClock()

        agent = launch_agent.wait_for_session(agent_with(None), lambda: agent_with(None),
                                              timeout_seconds=5, sleep=clock.sleep, clock=clock.time)

        self.assertIsNone(agent)
        self.assertEqual(clock.now, 5)


if __name__ == "__main__":
    unittest.main()
