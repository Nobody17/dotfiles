"""Run with python3 -m unittest discover -s '!tests' -p 'test_orchestrate_run_steps.py'.

Drives dispatch-worker.py, start-integration.py and finish-integration.py against a temporary Git
repository and a fake `herdr` that records its calls.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "agents/.agents/skills/orchestrate-tickets/scripts"
FAKE_HERDR = '''#!/usr/bin/env python3
import json, os, sys
arguments = sys.argv[1:]
with open(os.environ["FAKE_HERDR_LOG"], "a") as log:
    log.write(json.dumps(arguments) + "\\n")
command = " ".join(arguments[:2])
if command == "tab create":
    number = sum(1 for line in open(os.environ["FAKE_HERDR_LOG"]) if '"tab", "create"' in line)
    print(json.dumps({"result": {"root_pane": {"pane_id": f"w1:p{number}"}, "tab": {"tab_id": f"w1:t{number}"}}}))
elif command in ("agent start", "agent get"):
    print(json.dumps({"result": {"agent": {"agent_session": {"value": "session-1"}, "cwd": "/work"}}}))
elif command == "agent read":
    print(os.environ.get("FAKE_HERDR_SCREEN", "worktree  branch Opus 5.5 (95% left)"))
elif command == "pane report-metadata":
    print(json.dumps({"result": {}}))
'''


def git(repository, *arguments):
    return subprocess.run(["git", "-C", str(repository), *arguments], check=True, capture_output=True, text=True).stdout.strip()


class RunStepTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.root = Path(temporary_directory.name).resolve()
        self.repository, self.run_directory = self.root / "repository", self.root / "run"
        self.integration_worktree = self.root / "integration"
        tickets = self.root / "issues"
        for directory in (self.repository, tickets, self.root / "bin"):
            directory.mkdir()
        git(self.repository, "init", "--quiet", "--initial-branch", "dev")
        git(self.repository, "config", "user.email", "test@example.invalid")
        git(self.repository, "config", "user.name", "Test")
        (self.repository / "base.txt").write_text("base\n")
        git(self.repository, "add", "base.txt")
        git(self.repository, "commit", "--quiet", "-m", "base")
        self.base = git(self.repository, "rev-parse", "HEAD")
        git(self.repository, "worktree", "add", "--quiet", "-b", "integration", str(self.integration_worktree), self.base)
        (tickets / "01-first.md").write_text("# 01\n\n**Blocked by:** None\n")
        (tickets / "02-second.md").write_text("# 02\n\n**Blocked by:** 01\n")
        (self.root / "spec.md").write_text("spec\n")
        fake_herdr = self.root / "bin/herdr"
        fake_herdr.write_text(FAKE_HERDR)
        fake_herdr.chmod(0o755)
        self.herdr_log = self.root / "herdr.log"
        self.environment = {**os.environ, "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}", "HERDR_ENV": "1",
                            "FAKE_HERDR_LOG": str(self.herdr_log)}
        self.ledger_path = self.run_directory / "ledger.json"
        self.run_script("init-ledger.py", "--run", str(self.run_directory), "--repository", str(self.repository),
                        "--spec", str(self.root / "spec.md"), "--tickets", str(tickets), "--base-branch", "dev",
                        "--prefix", "tr-", "--workspace", "w1", with_ledger=False)
        ledger = self.ledger()
        ledger["config"].update(permission_mode="auto", review_skill="/skills/review.md")
        ledger["integration"].update(branch="integration", worktree=str(self.integration_worktree))
        ledger["validation"].update(test_command="run-tests", ticket_checks="tests", integration_fast_checks="fast tests")
        ledger["commands"]["worktree_create"] = "git worktree add -b {branch} {path} {base} && echo 'App: http://localhost:3209'"
        ledger["commands"]["worktree_facts"] = {"app_url": r"App: (\S+)"}
        for ticket in ledger["tickets"].values():
            ticket["scope"] = "the ticket scope"
        self.ledger_path.write_text(json.dumps(ledger))

    def run_script(self, script, *arguments, with_ledger=True, **environment):
        ledger_arguments = ["--ledger", str(self.ledger_path)] if with_ledger else []
        return subprocess.run([sys.executable, str(SCRIPTS / script), *ledger_arguments, *arguments],
                              capture_output=True, text=True, env={**self.environment, **environment}, timeout=60)

    def ledger(self):
        return json.loads(self.ledger_path.read_text())

    def herdr_calls(self):
        return [json.loads(line) for line in self.herdr_log.read_text().splitlines()] if self.herdr_log.exists() else []

    def ticket_worktree(self, ticket_id):
        return Path(f"{self.repository}-tr-t{ticket_id}")

    def submit_ticket(self, ticket_id, content="ticket work\n"):
        """Dispatch the ticket and commit its work, as a worker does."""
        dispatched = self.run_script("dispatch-worker.py", "--ticket", ticket_id)
        self.assertEqual(dispatched.returncode, 0, dispatched.stderr)
        worktree = self.ticket_worktree(ticket_id)
        (worktree / f"t{ticket_id}.txt").write_text(content)
        git(worktree, "add", f"t{ticket_id}.txt")
        git(worktree, "-c", "user.email=test@example.invalid", "-c", "user.name=Test", "commit", "--quiet", "-m", f"ticket {ticket_id}")
        return git(worktree, "rev-parse", "HEAD")

    def integrate(self, ticket_id, content="ticket work\n"):
        """Advance the integration branch by one rewritten ticket commit, as an integrator does."""
        (self.integration_worktree / f"t{ticket_id}.txt").write_text(content)
        git(self.integration_worktree, "add", f"t{ticket_id}.txt")
        git(self.integration_worktree, "-c", "user.email=test@example.invalid", "-c", "user.name=Test",
            "commit", "--quiet", "-m", f"integrated ticket {ticket_id}")
        return git(self.integration_worktree, "rev-parse", "HEAD")

    def test_dispatch_creates_the_worktree_records_it_and_starts_the_worker(self):
        result = self.run_script("dispatch-worker.py", "--ticket", "01")

        ticket = self.ledger()["tickets"]["01"]
        assignment = (self.run_directory / "assignments/t01.md").read_text()
        prompts = [call for call in self.herdr_calls() if call[:2] == ["agent", "prompt"]]
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([ticket["status"], ticket["start_sha"], ticket["branch"], ticket["app_url"]],
                         ["working", self.base, "tr/t01", "http://localhost:3209"])
        self.assertEqual(git(self.ticket_worktree("01"), "rev-parse", "HEAD"), self.base)
        self.assertIn(f"Starting SHA: {self.base}", assignment)
        self.assertIn("the ticket scope", assignment)
        self.assertEqual(self.ledger()["resources"]["sessions"][0]["name"], "tr-t01")
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0][2], "tr-t01")
        self.assertIn(str(self.run_directory / "assignments/t01.md"), prompts[0][3])
        self.assertIn("references/worker.md", prompts[0][3])

    def test_dispatch_refuses_a_ticket_whose_blocker_is_not_integrated(self):
        result = self.run_script("dispatch-worker.py", "--ticket", "02")

        self.assertEqual(result.returncode, 1)
        self.assertIn("waits for 01", result.stderr)
        self.assertEqual(self.ledger()["tickets"]["02"]["status"], "pending")
        self.assertFalse(self.ticket_worktree("02").exists())

    def test_dispatch_blocks_the_ticket_when_the_session_shows_another_model(self):
        result = self.run_script("dispatch-worker.py", "--ticket", "01", FAKE_HERDR_SCREEN="worktree Sonnet 5.5")

        ticket = self.ledger()["tickets"]["01"]
        self.assertEqual(result.returncode, 1)
        self.assertIn("model marker 'Opus 5.5'", result.stderr)
        self.assertEqual([ticket["status"], ticket["blocked"]["previous"]], ["blocked", "working"])
        self.assertEqual([call for call in self.herdr_calls() if call[:2] == ["agent", "prompt"]], [])

    def test_send_ticket_sends_only_the_ticket_path(self):
        self.run_script("dispatch-worker.py", "--ticket", "01")

        self.run_script("dispatch-worker.py", "--ticket", "01", "--send-ticket")

        self.assertEqual(self.herdr_calls()[-1], ["agent", "prompt", "tr-t01", str(self.root / "issues/01-first.md")])

    def test_start_integration_takes_the_lock_and_starts_the_integrator_with_the_note(self):
        submitted = self.submit_ticket("01")

        result = self.run_script("start-integration.py", "--ticket", "01", "--submitted", submitted, "--note", "expect a conflict in a.rb")

        ledger = self.ledger()
        assignment = (self.run_directory / "assignments/i01-1.md").read_text()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.run_directory / "integration.lock/owner").read_text(),
                         f"job i01-1\nagent tr-i01\nintegration_sha {self.base}\n")
        self.assertEqual([ledger["tickets"]["01"]["status"], ledger["integration"]["owner"], ledger["jobs"]["i01-1"]["status"]],
                         ["integrating", "i01-1", "running"])
        self.assertIn(f"submitted SHA: {submitted}", assignment)
        self.assertIn("## Addition from the orchestrator\nexpect a conflict in a.rb", assignment)
        self.assertEqual(self.herdr_calls()[-1][:3], ["agent", "prompt", "tr-i01"])

    def test_start_integration_refuses_an_occupied_slot_and_a_moved_branch(self):
        submitted = self.submit_ticket("01")
        (self.run_directory / "integration.lock").mkdir()
        (self.run_directory / "integration.lock/owner").write_text("job i09-1\n")

        occupied = self.run_script("start-integration.py", "--ticket", "01", "--submitted", submitted)
        (self.run_directory / "integration.lock/owner").unlink()
        (self.run_directory / "integration.lock").rmdir()
        moved = self.run_script("start-integration.py", "--ticket", "01", "--submitted", self.base)

        self.assertEqual(occupied.returncode, 1)
        self.assertIn("occupied: job i09-1", occupied.stderr)
        self.assertEqual(moved.returncode, 1)
        self.assertIn("the handoff submitted", moved.stderr)
        self.assertFalse((self.run_directory / "integration.lock").exists())
        self.assertEqual(self.ledger()["tickets"]["01"]["status"], "working")

    def test_finish_closes_sessions_releases_the_lock_and_retires_worktree_and_branch(self):
        submitted = self.submit_ticket("01")
        self.run_script("start-integration.py", "--ticket", "01", "--submitted", submitted)
        integrated = self.integrate("01")

        result = self.run_script("finish-integration.py", "--ticket", "01", "--integrated", integrated, "--close-tab", "w1:t9")

        ledger = self.ledger()
        closed_tabs = [call[2] for call in self.herdr_calls() if call[:2] == ["tab", "close"]]
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([ledger["tickets"]["01"]["status"], ledger["tickets"]["01"]["integrated_sha"]], ["integrated", integrated])
        self.assertEqual([ledger["integration"]["last_validated_sha"], ledger["integration"]["owner"]], [integrated, None])
        self.assertEqual(sorted(closed_tabs), ["w1:t1", "w1:t2", "w1:t9"])
        self.assertEqual({session["status"] for session in ledger["resources"]["sessions"]}, {"closed"})
        self.assertFalse((self.run_directory / "integration.lock").exists())
        self.assertFalse(self.ticket_worktree("01").exists())
        self.assertEqual(git(self.repository, "branch", "--list", "tr/*"), "")
        self.assertEqual(git(self.repository, "rev-parse", "refs/orchestrate/run/tr/t01"), submitted)

    def test_finish_refuses_when_the_integration_worktree_is_at_another_commit(self):
        submitted = self.submit_ticket("01")
        self.run_script("start-integration.py", "--ticket", "01", "--submitted", submitted)

        result = self.run_script("finish-integration.py", "--ticket", "01", "--integrated", submitted)

        self.assertEqual(result.returncode, 1)
        self.assertIn("integration worktree is at", result.stderr)
        self.assertEqual(self.ledger()["tickets"]["01"]["status"], "integrating")
        self.assertTrue((self.run_directory / "integration.lock").exists())

    def test_a_changed_patch_keeps_the_branch_until_the_rerun_with_accounted(self):
        submitted = self.submit_ticket("01")
        self.run_script("start-integration.py", "--ticket", "01", "--submitted", submitted)
        integrated = self.integrate("01", content="ticket work, adapted by the integrator\n")

        refused = self.run_script("finish-integration.py", "--ticket", "01", "--integrated", integrated)
        branch_after_refusal = git(self.repository, "rev-parse", "refs/heads/tr/t01")
        rerun = self.run_script("finish-integration.py", "--ticket", "01", "--integrated", integrated, "--accounted")

        self.assertEqual(refused.returncode, 1)
        self.assertIn("--accounted", refused.stderr)
        self.assertEqual(branch_after_refusal, submitted)
        self.assertEqual(self.ledger()["tickets"]["01"]["status"], "integrated")
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        self.assertIn("adapted by the integrator", rerun.stdout)
        self.assertEqual(git(self.repository, "branch", "--list", "tr/*"), "")
        self.assertEqual(git(self.repository, "rev-parse", "refs/orchestrate/run/tr/t01"), submitted)

    def test_the_next_ticket_dispatches_from_the_new_integration_tip(self):
        submitted = self.submit_ticket("01")
        self.run_script("start-integration.py", "--ticket", "01", "--submitted", submitted)
        integrated = self.integrate("01")
        self.run_script("finish-integration.py", "--ticket", "01", "--integrated", integrated)

        result = self.run_script("dispatch-worker.py", "--ticket", "02")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ledger()["tickets"]["02"]["start_sha"], integrated)


if __name__ == "__main__":
    unittest.main()
