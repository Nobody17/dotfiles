"""Run with python3 -m unittest discover -s '!tests' -p 'test_retire_resources.py'."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "agents/.agents/skills/orchestrate-tickets/scripts/retire-resources.py"
RECOVERY_PREFIX = "refs/orchestrate/test-run"


def git(repository, *arguments):
    return subprocess.run(
        ["git", "-C", str(repository), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def commit_file(repository, name, content, message):
    (Path(repository) / name).write_text(content)
    git(repository, "add", name)
    git(repository, "commit", "--quiet", "-m", message)
    return git(repository, "rev-parse", "HEAD")


class RetireResourcesTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.root = Path(temporary_directory.name).resolve()
        self.repository = self.root / "repository"
        self.repository.mkdir()
        git(self.repository, "init", "--quiet", "--initial-branch", "integration")
        git(self.repository, "config", "user.email", "test@example.invalid")
        git(self.repository, "config", "user.name", "Test")
        (self.repository / ".gitignore").write_text("cache/\n")
        git(self.repository, "add", ".gitignore")
        self.base = commit_file(self.repository, "base.txt", "base\n", "base")

    def add_ticket_worktree(self, name):
        """Create a ticket branch with one commit in its own worktree."""
        worktree = self.root / name
        git(self.repository, "worktree", "add", "--quiet", "-b", name, str(worktree), self.base)
        git(worktree, "config", "user.email", "test@example.invalid")
        tip = commit_file(worktree, f"{name}.txt", f"{name}\n", name)
        return worktree, tip

    def squash_onto_integration(self, file_name, content):
        """Advance integration by a rewritten commit, as an integrator does."""
        return commit_file(self.repository, file_name, content, "integrated ticket")

    def run_script(self, *arguments):
        destination_sha = git(self.repository, "rev-parse", "integration")
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.repository), "--destination", "integration",
             "--destination-sha", destination_sha, "--recovery-prefix", RECOVERY_PREFIX, *arguments],
            capture_output=True, text=True,
        )

    def ref(self, reference):
        result = subprocess.run(
            ["git", "-C", str(self.repository), "rev-parse", "--verify", "--quiet", reference],
            capture_output=True, text=True,
        )
        return result.stdout.strip() or None

    def test_branch_merged_by_ancestry_is_kept_in_recovery_ref_and_deleted_once(self):
        worktree, tip = self.add_ticket_worktree("t01")
        git(self.repository, "merge", "--quiet", "--ff-only", "t01")
        arguments = ("--worktree", str(worktree), "--branch", f"t01={tip}")

        result = self.run_script(*arguments)
        rerun = self.run_script(*arguments)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(worktree.exists())
        self.assertIsNone(self.ref("refs/heads/t01"))
        self.assertEqual(self.ref(f"{RECOVERY_PREFIX}/t01"), tip)
        report = json.loads(result.stdout)
        self.assertEqual(report["branches"][0]["action"], "deleted")
        self.assertEqual(report["worktrees"][0]["action"], "removed")
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        rerun_report = json.loads(rerun.stdout)
        self.assertEqual(rerun_report["worktrees"][0]["action"], "already removed")
        self.assertEqual(rerun_report["branches"][0]["action"], "already deleted")

    def test_squashed_branch_with_the_same_patch_is_deleted_after_an_interrupted_run(self):
        worktree, tip = self.add_ticket_worktree("t02")
        integrated = self.squash_onto_integration("t02.txt", "t02\n")
        git(self.repository, "update-ref", f"{RECOVERY_PREFIX}/t02", tip)

        result = self.run_script("--worktree", str(worktree), "--branch", f"t02={tip}",
                                 "--squash", f"t02={self.base}:{integrated}")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(self.ref("refs/heads/t02"))
        self.assertEqual(self.ref(f"{RECOVERY_PREFIX}/t02"), tip)

    def test_squashed_branch_with_a_different_patch_changes_nothing(self):
        worktree, tip = self.add_ticket_worktree("t03")
        integrated = self.squash_onto_integration("t03.txt", "something else\n")

        result = self.run_script("--worktree", str(worktree), "--branch", f"t03={tip}",
                                 "--squash", f"t03={self.base}:{integrated}")

        self.assertEqual(result.returncode, 1)
        self.assertIn("does not contain", result.stderr)
        self.assertTrue(worktree.exists())
        self.assertEqual(self.ref("refs/heads/t03"), tip)
        self.assertIsNone(self.ref(f"{RECOVERY_PREFIX}/t03"))

    def test_refusal_of_a_rewritten_branch_names_the_accounted_option(self):
        worktree, tip = self.add_ticket_worktree("t03")
        self.squash_onto_integration("t03.txt", "something else\n")

        result = self.run_script("--worktree", str(worktree), "--branch", f"t03={tip}")

        self.assertEqual(result.returncode, 1)
        self.assertIn("--accounted t03=<start>:<integrated>", result.stderr)

    def test_accounted_branch_with_a_changed_patch_is_deleted_and_reports_the_range_diff(self):
        worktree, tip = self.add_ticket_worktree("t05")
        integrated = self.squash_onto_integration("t05.txt", "t05, changed by the integrator\n")
        arguments = ("--worktree", str(worktree), "--branch", f"t05={tip}", "--accounted", f"t05={self.base}:{integrated}")

        dry_run = self.run_script(*arguments, "--dry-run")
        result = self.run_script(*arguments)

        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        self.assertEqual(self.ref("refs/heads/t05"), None if result.returncode == 0 else tip)
        planned = json.loads(dry_run.stdout)["branches"][0]
        self.assertEqual(planned["action"], "delete")
        self.assertIn("accounted by the caller", planned["proof"])
        self.assertTrue(any("changed by the integrator" in line for line in planned["range_diff"]), planned["range_diff"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(self.ref("refs/heads/t05"))
        self.assertEqual(self.ref(f"{RECOVERY_PREFIX}/t05"), tip)

    def test_accounted_needs_an_integrated_commit_in_the_destination(self):
        worktree, tip = self.add_ticket_worktree("t06")
        other_worktree, other_tip = self.add_ticket_worktree("elsewhere")

        result = self.run_script("--worktree", str(worktree), "--branch", f"t06={tip}",
                                 "--accounted", f"t06={self.base}:{other_tip}")

        self.assertEqual(result.returncode, 1)
        self.assertIn("does not contain", result.stderr)
        self.assertEqual(self.ref("refs/heads/t06"), tip)

    def test_dirty_worktree_stops_the_whole_run(self):
        merged_worktree, merged_tip = self.add_ticket_worktree("t04")
        git(self.repository, "merge", "--quiet", "--ff-only", "t04")
        dirty_worktree = self.root / "t05"
        git(self.repository, "worktree", "add", "--quiet", "-b", "t05", str(dirty_worktree), "integration")
        (dirty_worktree / "notes.txt").write_text("unsaved\n")

        result = self.run_script("--worktree", str(merged_worktree), "--worktree", str(dirty_worktree),
                                 "--branch", f"t04={merged_tip}")

        self.assertEqual(result.returncode, 1)
        self.assertIn("notes.txt", result.stderr)
        self.assertTrue(merged_worktree.exists())
        self.assertEqual(self.ref("refs/heads/t04"), merged_tip)

    def test_ignored_files_need_explicit_permission(self):
        worktree, tip = self.add_ticket_worktree("t06")
        git(self.repository, "merge", "--quiet", "--ff-only", "t06")
        (worktree / "cache").mkdir()
        (worktree / "cache" / "report.txt").write_text("unique report\n")

        refused = self.run_script("--worktree", str(worktree), "--branch", f"t06={tip}")
        allowed = self.run_script("--worktree", str(worktree), "--branch", f"t06={tip}", "--drop-ignored")

        self.assertEqual(refused.returncode, 1)
        self.assertIn("cache/", refused.stderr)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertFalse(worktree.exists())

    def test_branch_that_moved_after_the_handoff_is_preserved(self):
        worktree, tip = self.add_ticket_worktree("t07")
        git(self.repository, "merge", "--quiet", "--ff-only", "t07")
        newer_tip = commit_file(worktree, "late.txt", "late\n", "late change")

        result = self.run_script("--worktree", str(worktree), "--branch", f"t07={tip}")

        self.assertEqual(result.returncode, 1)
        self.assertIn("account for the new commits", result.stderr)
        self.assertEqual(self.ref("refs/heads/t07"), newer_tip)

    def test_moved_destination_stops_the_run(self):
        worktree, tip = self.add_ticket_worktree("t09")
        git(self.repository, "merge", "--quiet", "--ff-only", "t09")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.repository), "--destination", "integration",
             "--destination-sha", self.base, "--recovery-prefix", RECOVERY_PREFIX,
             "--worktree", str(worktree), "--branch", f"t09={tip}"],
            capture_output=True, text=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("expected", result.stderr)
        self.assertTrue(worktree.exists())


if __name__ == "__main__":
    unittest.main()
