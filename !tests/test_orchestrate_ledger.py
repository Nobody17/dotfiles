"""Run with python3 -m unittest discover -s '!tests' -p 'test_orchestrate_ledger.py'."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "agents/.agents/skills/orchestrate-tickets/scripts"
BLOCKED_TICKET = "# 03: Third\n\n**Blocked by:** 01, 02\n\n**Status:** ready-for-agent\n"
FREE_TICKET = "# 01: First\n\n**Blocked by:** None (can start immediately)\n"


def git(repository, *arguments):
    return subprocess.run(["git", "-C", str(repository), *arguments], check=True, capture_output=True, text=True).stdout.strip()


class LedgerTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.root = Path(temporary_directory.name).resolve()
        self.repository = self.root / "repository"
        self.tickets = self.root / "issues"
        self.run_directory = self.root / "run"
        self.repository.mkdir()
        self.tickets.mkdir()
        git(self.repository, "init", "--quiet", "--initial-branch", "dev")
        git(self.repository, "-c", "user.email=test@example.invalid", "-c", "user.name=Test",
            "commit", "--quiet", "--allow-empty", "-m", "base")
        (self.tickets / "01-first.md").write_text(FREE_TICKET)
        (self.tickets / "03-third.md").write_text(BLOCKED_TICKET)
        (self.tickets / "notes.md").write_text("no ticket\n")
        (self.root / "spec.md").write_text("spec\n")

    def init_ledger(self):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "init-ledger.py"), "--run", str(self.run_directory),
             "--repository", str(self.repository), "--spec", str(self.root / "spec.md"),
             "--tickets", str(self.tickets), "--base-branch", "dev", "--prefix", "tr-", "--workspace", "w1"],
            capture_output=True, text=True)

    def ledger(self):
        return json.loads((self.run_directory / "ledger.json").read_text())

    def render(self, template_text):
        template, output = self.root / "template.md", self.root / "assignment.md"
        template.write_text(template_text)
        result = subprocess.run([sys.executable, str(SCRIPTS / "render-assignment.py"), str(template), str(output),
                                 "--ledger", str(self.run_directory / "ledger.json")], capture_output=True, text=True)
        return result, output

    def test_starts_a_ledger_with_the_base_from_git_and_one_entry_per_ticket(self):
        result = self.init_ledger()

        ledger = self.ledger()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(ledger["base_sha"], git(self.repository, "rev-parse", "dev"))
        self.assertEqual(sorted(ledger["tickets"]), ["01", "03"])
        self.assertEqual([ledger["tickets"]["01"]["depends_on"], ledger["tickets"]["03"]["depends_on"]], [[], ["01", "02"]])
        self.assertEqual(ledger["tickets"]["03"]["agent_name"], "tr-t03")
        self.assertTrue((self.run_directory / "handoffs").is_dir() and (self.run_directory / "assignments/templates").is_dir())
        self.assertIn("validation.test_command", result.stdout)

    def test_base_check_prints_a_line_only_after_the_base_branch_moved(self):
        self.init_ledger()
        check = next(check for check in self.ledger()["resource_watch"]["checks"] if check["name"] == "base")

        before = subprocess.run(check["command"], shell=True, capture_output=True, text=True)
        git(self.repository, "-c", "user.email=test@example.invalid", "-c", "user.name=Test",
            "commit", "--quiet", "--allow-empty", "-m", "moved")
        after = subprocess.run(check["command"], shell=True, capture_output=True, text=True)

        self.assertEqual([before.returncode, before.stdout], [0, ""])
        self.assertEqual(after.returncode, 0)
        self.assertRegex(after.stdout, check["match"] + ": " + git(self.repository, "rev-parse", "dev"))

    def test_refuses_to_replace_an_existing_ledger(self):
        self.init_ledger()

        result = self.init_ledger()

        self.assertEqual(result.returncode, 1)
        self.assertIn("exists", result.stderr)

    def test_render_refuses_a_command_that_lost_a_required_text(self):
        self.init_ledger()
        ledger = self.ledger()
        ledger["validation"]["test_command"] = "env DATAe38b3c2e_URL=postgres://db PARALLEL_WORKERS=2 bin/rails test"
        ledger["validation"]["must_contain"] = {"test_command": ["DATABASE_URL=", "PARALLEL_WORKERS=2"]}
        (self.run_directory / "ledger.json").write_text(json.dumps(ledger))

        result, output = self.render("Tests: {{ledger.validation.test_command}}\n")

        self.assertEqual(result.returncode, 1)
        self.assertIn("validation.test_command does not contain 'DATABASE_URL='", result.stderr)
        self.assertFalse(output.exists())

    def test_render_writes_the_assignment_when_the_commands_are_intact(self):
        self.init_ledger()
        ledger = self.ledger()
        ledger["validation"]["test_command"] = "env DATABASE_URL=postgres://db bin/rails test"
        ledger["validation"]["must_contain"] = {"test_command": ["DATABASE_URL="]}
        (self.run_directory / "ledger.json").write_text(json.dumps(ledger))

        result, output = self.render("Tests: {{ledger.validation.test_command}} in {{run}}\n")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text(), f"Tests: env DATABASE_URL=postgres://db bin/rails test in {self.run_directory}\n")


if __name__ == "__main__":
    unittest.main()
