"""Run with python3 -m unittest discover -s '!tests' -p 'test_orchestrate_watch_run.py'."""

import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "agents/.agents/skills/orchestrate-tickets/scripts/watch-run.py"
SPECIFICATION = importlib.util.spec_from_file_location("watch_run", SCRIPT)
watch_run = importlib.util.module_from_spec(SPECIFICATION)
SPECIFICATION.loader.exec_module(watch_run)

AGENT_COMMAND = "claude --model claude-opus-5-5 --settings {\"promptSuggestionEnabled\": false} --name ns-t03"
TOOL_SHELL = "/bin/zsh -c source /Users/someone/.claude/shell-snapshots/snapshot-zsh-1.sh && eval 'bin/rails test'"


class ResourceCheckTests(unittest.TestCase):
    def test_reports_a_minimum_check_once_per_drop(self):
        check = {"name": "memory-mb", "command": "unused", "minimum": 1000}
        first_events, state = watch_run.resource_events([check], {}, lambda _command: ("800\n", ""))
        repeated_events, state = watch_run.resource_events([check], state, lambda _command: ("700\n", ""))
        recovered_events, state = watch_run.resource_events([check], state, lambda _command: ("2000\n", ""))
        second_drop_events, _state = watch_run.resource_events([check], state, lambda _command: ("900\n", ""))
        self.assertEqual(first_events, ["resource memory-mb 800 below 1000"])
        self.assertEqual(repeated_events, [])
        self.assertEqual(recovered_events, [])
        self.assertEqual(second_drop_events, ["resource memory-mb 900 below 1000"])

    def test_takes_existing_log_lines_as_seen_and_reports_new_matches(self):
        check = {"name": "oom", "command": "unused", "match": "Killed process"}
        old_log = "[113122.1] Out of memory: Killed process 12 (ruby)\n[113200.0] eth0 up\n"
        new_log = old_log + "[113355.4] Out of memory: Killed process 34 (ruby)\n"
        first_events, state = watch_run.resource_events([check], {}, lambda _command: (old_log, ""))
        new_events, state = watch_run.resource_events([check], state, lambda _command: (new_log, ""))
        repeated_events, _state = watch_run.resource_events([check], state, lambda _command: (new_log, ""))
        self.assertEqual(first_events, [])
        self.assertEqual(new_events, ["resource oom new: [113355.4] Out of memory: Killed process 34 (ruby)"])
        self.assertEqual(repeated_events, [])

    def test_reports_no_old_line_again_in_a_long_log(self):
        check = {"name": "oom", "command": "unused", "match": "Killed process"}
        long_log = "".join(f"[{number}.0] Out of memory: Killed process {number} (ruby)\n" for number in range(800))
        _events, state = watch_run.resource_events([check], {}, lambda _command: (long_log, ""))
        repeated_events, _state = watch_run.resource_events([check], state, lambda _command: (long_log, ""))
        self.assertEqual(repeated_events, [])

    def test_reports_a_failing_check_once_per_failure_streak(self):
        check = {"name": "memory-mb", "command": "unused", "minimum": 1000}
        first_events, state = watch_run.resource_events([check], {}, lambda _command: (None, "exit 1: no docker"))
        repeated_events, _state = watch_run.resource_events([check], state, lambda _command: (None, "exit 1: no docker"))
        self.assertEqual(first_events, ["resource memory-mb failed: exit 1: no docker"])
        self.assertEqual(repeated_events, [])


class IdleShellTests(unittest.TestCase):
    def test_counts_only_the_shell_children_of_the_named_agent(self):
        table = [
            (100, 1, AGENT_COMMAND),
            (101, 100, TOOL_SHELL),
            (102, 100, "bash /Users/someone/.claude/statusline-command.sh"),
            (103, 100, "caffeinate -i -t 300"),
            (200, 1, AGENT_COMMAND.replace("ns-t03", "ns-t030")),
            (201, 200, TOOL_SHELL),
        ]
        self.assertEqual(watch_run.running_shells(table, "ns-t03"), 1)
        self.assertEqual(watch_run.running_shells(table, "ns-t05"), 0)

    def test_reports_an_idle_agent_with_shells_once_after_the_limit(self):
        agents = {"ns-t03": "idle", "ns-t05": "done", "ns-t06": "working"}
        shells = {"ns-t03": 2, "ns-t05": 0, "ns-t06": 1}
        early_events, state = watch_run.idle_shell_events({}, agents, shells, now=1000, limit_seconds=600)
        late_events, state = watch_run.idle_shell_events(state, agents, shells, now=1700, limit_seconds=600)
        repeated_events, state = watch_run.idle_shell_events(state, agents, shells, now=2500, limit_seconds=600)
        self.assertEqual(early_events, [])
        self.assertEqual(late_events, ["agent ns-t03 idle 12 min with 2 shells"])
        self.assertEqual(repeated_events, [])
        self.assertEqual(list(state), ["ns-t03"])

    def test_starts_a_new_idle_period_after_the_agent_works(self):
        state = {"ns-t03": {"since": 0, "reported": True}}
        _events, state = watch_run.idle_shell_events(state, {"ns-t03": "working"}, {"ns-t03": 1}, now=100, limit_seconds=60)
        self.assertEqual(state, {})


class JobRecordTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.run_directory = Path(temporary_directory.name).resolve()
        (self.run_directory / "heavy-jobs").mkdir()
        self.now = datetime.datetime.now(datetime.timezone.utc)

    def write_record(self, job, **fields):
        record = {"job": job, "label": "area tests", "pid": os.getpid(), "process_group": 42,
                  "started": self.now.isoformat(), "review_at": (self.now + datetime.timedelta(hours=1)).isoformat(),
                  "last_output": self.now.isoformat(), **fields}
        (self.run_directory / "heavy-jobs" / f"{job}.json").write_text(json.dumps(record))

    def test_keeps_the_record_of_an_ended_wrapper_and_reports_it_once(self):
        self.write_record("7", pid=2 ** 22 + 12345)
        events, reported = watch_run.job_events(self.run_directory, [], self.now.timestamp())
        repeated_events, _reported = watch_run.job_events(self.run_directory, reported, self.now.timestamp())
        self.assertEqual(events, ["job 7 area tests left by ended wrapper; group 42 can still run"])
        self.assertEqual(repeated_events, [])
        self.assertTrue((self.run_directory / "heavy-jobs" / "7.json").exists())

    def test_reports_each_failed_cleanup_attempt(self):
        self.write_record("8", state="cleanup failed", cleanup_attempts=1)
        first_events, reported = watch_run.job_events(self.run_directory, [], self.now.timestamp())
        self.write_record("8", state="cleanup failed", cleanup_attempts=2)
        second_events, _reported = watch_run.job_events(self.run_directory, reported, self.now.timestamp())
        self.assertEqual(first_events, ["job 8 area tests cleanup failed (attempt 1); slot held until --stop or --release"])
        self.assertEqual(second_events, ["job 8 area tests cleanup failed (attempt 2); slot held until --stop or --release"])


class WatchRunCommandTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.root = Path(temporary_directory.name).resolve()
        self.run_directory = self.root / "run"
        (self.run_directory / "handoffs").mkdir(parents=True)
        binaries = self.root / "bin"
        binaries.mkdir()
        fake_herdr = binaries / "herdr"
        fake_herdr.write_text("#!/bin/sh\necho '{\"result\": {\"agents\": []}}'\n")
        fake_herdr.chmod(0o755)
        self.environment = {**os.environ, "PATH": f"{binaries}:{os.environ['PATH']}"}

    def watch_once(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.run_directory), "--prefix", "ns-", "--once"],
            capture_output=True, text=True, env=self.environment, timeout=30,
        )

    def test_reads_an_old_state_file_and_reports_resource_and_job_alarms(self):
        (self.run_directory / "watch-state.json").write_text(json.dumps({"files": [], "agents": {}}))
        (self.run_directory / "ledger.json").write_text(json.dumps({"resource_watch": {"checks": [
            {"name": "disk-gb", "command": "echo 3", "minimum": 8},
        ]}}))
        jobs = self.run_directory / "heavy-jobs"
        jobs.mkdir()
        now = datetime.datetime.now(datetime.timezone.utc)
        (jobs / "1.json").write_text(json.dumps({
            "job": "1", "label": "area tests", "pid": os.getpid(), "process_group": 42,
            "started": (now - datetime.timedelta(minutes=50)).isoformat(),
            "review_at": (now - datetime.timedelta(minutes=10)).isoformat(),
            "last_output": (now - datetime.timedelta(minutes=45)).isoformat(),
        }))
        result = self.watch_once()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "resource disk-gb 3 below 8",
            "job 1 area tests needs a review: running 50 min, last output 45 min ago",
        ])
        state = json.loads((self.run_directory / "watch-state.json").read_text())
        self.assertTrue(state["checks"]["disk-gb"]["below"])
        self.assertEqual(len(state["jobs_reported"]), 1)
        self.assertTrue(state["jobs_reported"][0].startswith("1@"))


if __name__ == "__main__":
    unittest.main()
