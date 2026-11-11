"""Run with python3 -m unittest discover -s '!tests' -p 'test_orchestrate_heavy_job.py'."""

import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "agents/.agents/skills/orchestrate-tickets/scripts/heavy-job.py"


class HeavyJobTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.run_directory = Path(temporary_directory.name).resolve()

    def write_policy(self, **policy):
        (self.run_directory / "ledger.json").write_text(json.dumps({"heavy_jobs": policy}))

    def wrapper_command(self, *arguments):
        return [sys.executable, str(SCRIPT), "--run", str(self.run_directory), *arguments]

    def run_wrapper(self, *arguments):
        return subprocess.run(self.wrapper_command(*arguments), capture_output=True, text=True,
                              cwd=self.run_directory, timeout=30)

    def hold_lock(self, name):
        descriptor = os.open(self.run_directory / name, os.O_RDWR | os.O_CREAT)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        return descriptor

    def start_wrapper(self, *arguments):
        return subprocess.Popen(self.wrapper_command(*arguments), cwd=self.run_directory,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def wait_for_record(self):
        for _attempt in range(50):
            records = [path for path in (self.run_directory / "heavy-jobs").glob("*.json")
                       if ".request-" not in path.name]
            if records:
                return json.loads(records[0].read_text())
            time.sleep(0.1)
        self.fail("the job wrote no record")

    def test_passes_the_command_exit_code_through_and_keeps_the_log(self):
        self.write_policy(review_after_minutes=1)
        result = self.run_wrapper("--label", "exit-three", "--", "sh", "-c", "echo progress; exit 3")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("slot 1/1", result.stderr)
        self.assertEqual(result.stdout, "progress\n")
        jobs = self.run_directory / "heavy-jobs"
        self.assertEqual(list(jobs.glob("*.json")), [])
        self.assertEqual([log.read_text() for log in jobs.glob("*.log")], ["progress\n"])

    def history(self):
        lines = (self.run_directory / "heavy-jobs" / "history.jsonl").read_text().splitlines()
        return [json.loads(line) for line in lines]

    def test_adds_each_ended_job_to_the_history(self):
        self.write_policy(review_after_minutes=1)
        self.run_wrapper("--label", "first", "--", "sh", "-c", "exit 3")
        self.run_wrapper("--label", "second", "--", "true")

        first, second = self.history()

        self.assertEqual([first["label"], first["exit"], second["label"], second["exit"]], ["first", 3, "second", 0])
        self.assertEqual(first["cwd"], str(self.run_directory))
        self.assertGreaterEqual(first["run_seconds"], 0)
        self.assertEqual(first["waited_seconds"], 0)
        self.assertNotIn("memory_peak_mb", first)

    def test_records_the_memory_peak_from_the_probe(self):
        probe = ("n=$(cat probe-count 2>/dev/null || echo 0); echo $((n + 1)) > probe-count; "
                 "echo $((1000 - n * 100)) MB")
        self.write_policy(review_after_minutes=1, memory_probe=probe, memory_probe_seconds=0.2)

        result = self.run_wrapper("--label", "probed", "--", "sleep", "1.5")

        entry = self.history()[0]
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(entry["memory_available_before_mb"], 1000)
        self.assertLess(entry["memory_available_lowest_mb"], 1000)
        self.assertEqual(entry["memory_peak_mb"], 1000 - entry["memory_available_lowest_mb"])

    def test_a_failing_memory_probe_leaves_the_job_and_its_history_intact(self):
        self.write_policy(review_after_minutes=1, memory_probe="exit 1", memory_probe_seconds=0.2)

        result = self.run_wrapper("--label", "no-probe", "--", "true")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("memory_peak_mb", self.history()[0])

    def test_refuses_a_job_without_review_time(self):
        result = self.run_wrapper("--", "true")
        self.assertEqual(result.returncode, 125)
        self.assertIn("no review time", result.stderr)

    def test_reports_a_missing_command_with_exit_127(self):
        self.write_policy(review_after_minutes=1)
        result = self.run_wrapper("--", "no-such-command-for-heavy-job-test")
        self.assertEqual(result.returncode, 127, result.stderr)

    def test_marks_a_long_job_for_review_and_lets_it_finish(self):
        self.write_policy(review_after_minutes=0.01)
        result = self.run_wrapper("--label", "slow", "--", "sh", "-c", "sleep 3; exit 0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("needs a review, the job continues", result.stderr)

    def test_stops_a_job_on_request_runs_the_cleanup_and_exits_124(self):
        self.write_policy(review_after_minutes=0.01, stop_cleanup="touch cleaned")
        process = self.start_wrapper("--kill-after-seconds", "1", "--label", "hang", "--",
                                     "sh", "-c", "trap '' TERM; sleep 60 & wait")
        record = self.wait_for_record()
        listing = self.run_wrapper("--list")
        self.assertIn(f"job {record['job']} hang", listing.stdout)
        self.assertIn("sleep 60", listing.stdout)
        stop = self.run_wrapper("--stop", record["job"], "--reason", "OOM killed a test worker")
        self.assertEqual(stop.returncode, 0, stop.stderr)
        _output, errors = process.communicate(timeout=20)
        self.assertEqual(process.returncode, 124, errors)
        self.assertIn("stop requested: OOM killed a test worker", errors)
        self.assertTrue((self.run_directory / "cleaned").exists())

    def test_extend_moves_the_review_time(self):
        self.write_policy(review_after_minutes=0.01)
        process = self.start_wrapper("--", "sleep", "4")
        record = self.wait_for_record()
        extend = self.run_wrapper("--extend", record["job"], "--minutes", "10")
        self.assertEqual(extend.returncode, 0, extend.stderr)
        time.sleep(3)
        later = self.wait_for_record()
        self.assertGreater(later["review_at"], record["review_at"])
        self.assertFalse(later["overdue"])
        process.communicate(timeout=20)
        self.assertEqual(process.returncode, 0)

    def test_options_override_the_ledger_policy(self):
        self.write_policy(review_after_minutes=60)
        result = self.run_wrapper("--review-after-minutes", "0.01", "--", "sleep", "3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("needs a review", result.stderr)

    def test_a_signal_to_the_wrapper_stops_the_job_and_runs_the_cleanup(self):
        self.write_policy(review_after_minutes=1, stop_cleanup="touch cleaned")
        process = self.start_wrapper("--kill-after-seconds", "1", "--", "sleep", "60")
        self.wait_for_record()
        process.terminate()
        _output, errors = process.communicate(timeout=20)
        self.assertEqual(process.returncode, 128 + 15, errors)
        self.assertTrue((self.run_directory / "cleaned").exists())

    def test_a_failed_cleanup_keeps_the_slot_until_release(self):
        self.write_policy(review_after_minutes=1, stop_cleanup="exit 1")
        process = self.start_wrapper("--kill-after-seconds", "1", "--", "sleep", "60")
        record = self.wait_for_record()
        self.run_wrapper("--stop", record["job"])
        for _attempt in range(50):
            if self.wait_for_record().get("state") == "cleanup failed":
                break
            time.sleep(0.2)
        self.assertEqual(self.wait_for_record()["state"], "cleanup failed")
        self.assertIsNone(process.poll())
        self.run_wrapper("--release", record["job"])
        _output, errors = process.communicate(timeout=20)
        self.assertEqual(process.returncode, 124, errors)
        self.assertIn("slot released by request", errors)

    def test_holds_the_slot_while_processes_of_the_group_still_run(self):
        self.write_policy(review_after_minutes=1)
        started = time.monotonic()
        result = self.run_wrapper("--", "sh", "-c", "sleep 3 > /dev/null 2>&1 & exit 0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreater(time.monotonic() - started, 2.5)
        self.assertIn("processes of its group still run", result.stderr)

    def test_a_waiting_job_takes_a_lowered_slot_count(self):
        self.write_policy(review_after_minutes=1, slots=2)
        first, second = self.hold_lock("heavy-job.lock"), self.hold_lock("heavy-job.lock.1")
        process = subprocess.Popen(self.wrapper_command("--", "true"), stderr=subprocess.PIPE, text=True)
        time.sleep(0.5)
        self.write_policy(review_after_minutes=1, slots=1)
        os.close(second)
        time.sleep(3)
        self.assertIsNone(process.poll(), "the job took slot 2 after the slot count fell to 1")
        os.close(first)
        _output, errors = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, errors)
        self.assertIn("slot 1/1", errors)

    def test_a_job_in_a_removed_slot_still_counts_as_busy(self):
        self.write_policy(review_after_minutes=1, slots=1)
        removed_slot = self.hold_lock("heavy-job.lock.1")
        process = subprocess.Popen(self.wrapper_command("--", "true"), stderr=subprocess.PIPE, text=True)
        time.sleep(1)
        self.assertIsNone(process.poll(), "the job started while a job in a removed slot still ran")
        os.close(removed_slot)
        _output, errors = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, errors)

    def test_a_stop_after_an_extend_is_not_lost(self):
        self.write_policy(review_after_minutes=1)
        process = self.start_wrapper("--kill-after-seconds", "1", "--", "sleep", "60")
        record = self.wait_for_record()
        self.run_wrapper("--extend", record["job"], "--minutes", "10")
        self.run_wrapper("--stop", record["job"])
        _output, errors = process.communicate(timeout=20)
        self.assertEqual(process.returncode, 124, errors)

    def test_control_commands_refuse_an_unknown_job(self):
        result = self.run_wrapper("--stop", "999999")
        self.assertEqual(result.returncode, 125)
        self.assertIn("no running job", result.stderr)

    def test_waits_while_the_only_slot_is_held(self):
        self.write_policy(review_after_minutes=1)
        holder = self.hold_lock("heavy-job.lock")
        process = subprocess.Popen(self.wrapper_command("--label", "waiting", "--", "true"),
                                   stderr=subprocess.PIPE, text=True)
        time.sleep(1)
        self.assertIsNone(process.poll(), "the job ran although its only slot was held")
        os.close(holder)
        _output, errors = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, errors)
        self.assertIn("waiting for a free slot", errors)

    def test_takes_the_second_slot_when_the_first_is_held(self):
        self.write_policy(review_after_minutes=1, slots=2, lock=str(self.run_directory / "test.lock"))
        holder = self.hold_lock("test.lock")
        self.addCleanup(os.close, holder)
        result = self.run_wrapper("--", "true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("slot 2/2", result.stderr)
        self.assertTrue((self.run_directory / "test.lock.1").exists())

    @unittest.skipUnless(shutil.which("lockf") and sys.platform == "darwin", "macOS lockf(1) only")
    def test_shares_slot_zero_with_macos_lockf(self):
        self.write_policy(review_after_minutes=1, lock=str(self.run_directory / "test.lock"))
        holder = subprocess.Popen(["lockf", "-k", str(self.run_directory / "test.lock"), "sleep", "2"])
        self.addCleanup(holder.wait)
        time.sleep(0.5)
        started = time.monotonic()
        result = self.run_wrapper("--", "true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreater(time.monotonic() - started, 1)
        self.assertIn("waiting for a free slot", result.stderr)


if __name__ == "__main__":
    unittest.main()
