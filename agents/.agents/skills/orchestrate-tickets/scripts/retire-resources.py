#!/usr/bin/env python3
"""Remove integrated worktrees and local branches after recovery refs keep their tips.

Every check runs before the first change, so a refused run changes nothing.
A rerun after an interruption skips the steps that are already done.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

UNFINISHED_OPERATION_FILES = (
    "rebase-merge",
    "rebase-apply",
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "BISECT_LOG",
)


class RetirementRefused(Exception):
    pass


def run_git(repository, *arguments, stdin=None, check=True):
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        input=stdin,
        check=check,
        capture_output=True,
        text=True,
    )


def git_output(repository, *arguments):
    return run_git(repository, *arguments).stdout.strip()


def all_refs(repository):
    """Map every ref name to its object, read in one Git call."""
    listing = git_output(repository, "for-each-ref", "--format=%(refname) %(objectname)")
    return dict(line.split(" ", 1) for line in listing.splitlines())


def resolve_commits(repository, revisions):
    """Resolve revisions to full commit IDs in one Git call, keeping their order."""
    if not revisions:
        return []
    for revision in revisions:
        if revision.startswith("-"):
            raise RetirementRefused(f"Expected a commit, received {revision!r}")
    output = git_output(repository, "rev-parse", *(f"{revision}^{{commit}}" for revision in revisions))
    return output.splitlines()


def is_ancestor(repository, commit, descendant):
    return run_git(repository, "merge-base", "--is-ancestor", commit, descendant, check=False).returncode == 0


def patch_id(repository, old_commit, new_commit):
    diff = git_output(repository, "diff", "--binary", old_commit, new_commit)
    return run_git(repository, "patch-id", "--stable", stdin=diff + "\n").stdout.split(" ")[0]


def registered_worktrees(repository):
    """Map each registered worktree path to its checked-out branch ref, or None."""
    worktrees = {}
    current_path = None
    for line in git_output(repository, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            current_path = str(Path(line.removeprefix("worktree ")).resolve())
            worktrees[current_path] = None
        elif line.startswith("branch ") and current_path is not None:
            worktrees[current_path] = line.removeprefix("branch ")
    return worktrees


def parse_pair(text, separator, label):
    left, found, right = text.partition(separator)
    if not found or not left.strip() or not right.strip():
        raise RetirementRefused(f"Expected {label}, received {text!r}")
    return left.strip(), right.strip()


def worktree_problems(worktree_path, allow_ignored):
    status = run_git(worktree_path, "status", "--porcelain", "--ignored").stdout.splitlines()
    changes = [line for line in status if not line.startswith("!! ")]
    ignored = [line[3:] for line in status if line.startswith("!! ")]
    problems = []
    if changes:
        problems.append(f"uncommitted or untracked files: {', '.join(line[3:] for line in changes)}")
    if ignored and not allow_ignored:
        problems.append(f"ignored files (save them, then pass --drop-ignored): {', '.join(ignored)}")
    git_directory = Path(git_output(worktree_path, "rev-parse", "--absolute-git-dir"))
    unfinished = [name for name in UNFINISHED_OPERATION_FILES if (git_directory / name).exists()]
    if unfinished:
        problems.append(f"unfinished Git operation: {', '.join(unfinished)}")
    return problems


def rewritten_commit_in_destination(repository, tip, destination_sha, rewrite):
    """True when the branch starts at rewrite's start commit and its integrated commit is in the destination."""
    start_commit, integrated_commit = rewrite
    return is_ancestor(repository, start_commit, tip) and is_ancestor(repository, integrated_commit, destination_sha)


def range_diff_lines(repository, start_commit, tip, integrated_commit):
    # The creation factor pairs the commits also when the integrator changed much of a small patch.
    return git_output(repository, "range-diff", "--no-color", "--creation-factor=100", f"{start_commit}..{tip}",
                      f"{integrated_commit}^..{integrated_commit}").splitlines()


def branch_integration_proof(repository, tip, destination_sha, squash_proof, accounted_proof=None):
    """Return (how the branch's complete work reached the destination, range-diff lines or None), or None.

    A squash proof needs the same patch. An accounted proof accepts a changed patch: the caller states that
    every difference (conflict resolution, a line adapted to another ticket) is checked and reviewed; the
    range-diff goes into the plan as the evidence for the ledger."""
    if is_ancestor(repository, tip, destination_sha):
        return "ancestor of destination", None
    if squash_proof is not None and rewritten_commit_in_destination(repository, tip, destination_sha, squash_proof):
        start_commit, integrated_commit = squash_proof
        if patch_id(repository, start_commit, tip) == patch_id(repository, f"{integrated_commit}^", integrated_commit):
            return f"same patch as integrated commit {integrated_commit}", None
    if accounted_proof is not None and rewritten_commit_in_destination(repository, tip, destination_sha, accounted_proof):
        start_commit, integrated_commit = accounted_proof
        return (f"rewritten as integrated commit {integrated_commit}; differences accounted by the caller",
                range_diff_lines(repository, start_commit, tip, integrated_commit))
    return None


def plan_retirement(repository, destination, destination_sha, recovery_prefix, worktrees, branches, squash_proofs,
                    allow_ignored, accounted_proofs=None):
    accounted_proofs = accounted_proofs or {}
    refs = all_refs(repository)
    current_destination = refs.get(f"refs/heads/{destination}")
    if current_destination != destination_sha:
        raise RetirementRefused(
            f"Destination {destination} is at {current_destination}, expected {destination_sha}"
        )

    registered = registered_worktrees(repository)
    worktree_steps = []
    for worktree in worktrees:
        worktree_path = str(Path(worktree).resolve())
        if worktree_path not in registered:
            worktree_steps.append({"path": worktree_path, "action": "already removed"})
            continue
        problems = worktree_problems(worktree_path, allow_ignored)
        if problems:
            raise RetirementRefused(f"Worktree {worktree_path} stays: {'; '.join(problems)}")
        worktree_steps.append({"path": worktree_path, "action": "remove"})

    removed_paths = {step["path"] for step in worktree_steps}
    branches_in_use = {
        branch_ref for path, branch_ref in registered.items() if path not in removed_paths and branch_ref
    }

    branch_steps = []
    for branch, expected_tip in branches:
        branch_ref = f"refs/heads/{branch}"
        recovery_ref = f"{recovery_prefix}/{branch}"
        current_tip = refs.get(branch_ref)
        recovered_tip = refs.get(recovery_ref)
        if current_tip is None:
            if recovered_tip == expected_tip:
                branch_steps.append({"branch": branch, "tip": expected_tip, "recovery_ref": recovery_ref, "action": "already deleted"})
                continue
            raise RetirementRefused(f"Branch {branch} is missing and {recovery_ref} does not keep {expected_tip}")
        if current_tip != expected_tip:
            raise RetirementRefused(f"Branch {branch} is at {current_tip}, expected {expected_tip}; account for the new commits first")
        if recovered_tip not in (None, expected_tip):
            raise RetirementRefused(f"{recovery_ref} already points to {recovered_tip}")
        if branch_ref in branches_in_use:
            raise RetirementRefused(f"Branch {branch} is checked out in a worktree that stays")
        proof = branch_integration_proof(repository, expected_tip, destination_sha, squash_proofs.get(branch),
                                         accounted_proofs.get(branch))
        if proof is None:
            raise RetirementRefused(
                f"Branch {branch} has work that {destination} does not contain. If an integrator rewrote it "
                f"with changes, check `git range-diff <start>..{branch} <integrated>^..<integrated>`, "
                f"then pass --accounted {branch}=<start>:<integrated>")
        proof_text, range_diff = proof
        step = {"branch": branch, "tip": expected_tip, "recovery_ref": recovery_ref,
                "recovery_ref_exists": recovered_tip is not None, "proof": proof_text, "action": "delete"}
        if range_diff is not None:
            step["range_diff"] = range_diff
        branch_steps.append(step)

    return {"destination": destination, "destination_sha": destination_sha, "worktrees": worktree_steps, "branches": branch_steps}


def apply_retirement(repository, plan):
    """Keep every tip in a recovery ref first, then remove worktrees, then delete branches."""
    branches_to_delete = [step for step in plan["branches"] if step["action"] == "delete"]
    worktrees_to_remove = [step for step in plan["worktrees"] if step["action"] == "remove"]

    for step in branches_to_delete:
        # The empty old value makes Git refuse when the recovery ref appeared meanwhile.
        if not step.pop("recovery_ref_exists"):
            git_output(repository, "update-ref", step["recovery_ref"], step["tip"], "")

    for step in worktrees_to_remove:
        # Git refuses changed and untracked files here, and deletes ignored files.
        git_output(repository, "worktree", "remove", step["path"])
        step["action"] = "removed"

    for step in branches_to_delete:
        git_output(repository, "update-ref", "-d", f"refs/heads/{step['branch']}", step["tip"])
        step["action"] = "deleted"

    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--destination", required=True, help="branch that must contain the work, without refs/heads/")
    parser.add_argument("--destination-sha", required=True)
    parser.add_argument("--recovery-prefix", required=True, help="for example refs/orchestrate/<run>")
    parser.add_argument("--worktree", action="append", default=[], metavar="PATH")
    parser.add_argument("--branch", action="append", default=[], metavar="NAME=TIP")
    parser.add_argument("--squash", action="append", default=[], metavar="NAME=START:INTEGRATED",
                        help="proof for a branch whose work reached the destination as a rewritten commit")
    parser.add_argument("--accounted", action="append", default=[], metavar="NAME=START:INTEGRATED",
                        help="proof for a rewritten branch whose patch changed (conflict resolution, adapted lines): "
                             "you checked every difference; the plan prints the range-diff as evidence")
    parser.add_argument("--drop-ignored", action="store_true", help="remove worktrees even when they hold ignored files")
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    try:
        repository = arguments.repo
        branch_pairs = [parse_pair(text, "=", "NAME=TIP") for text in arguments.branch]
        rewrite_pairs = []
        for text in [*arguments.squash, *arguments.accounted]:
            name, commits = parse_pair(text, "=", "NAME=START:INTEGRATED")
            rewrite_pairs.append((name, *parse_pair(commits, ":", "START:INTEGRATED")))
        revisions = [arguments.destination_sha, *(tip for _, tip in branch_pairs),
                     *(commit for _, start, integrated in rewrite_pairs for commit in (start, integrated))]
        destination_commit, *commits = resolve_commits(repository, revisions)
        branches = [(name, commits.pop(0)) for name, _ in branch_pairs]
        rewrite_proofs = [(name, (commits.pop(0), commits.pop(0))) for name, _, _ in rewrite_pairs]
        squash_proofs = dict(rewrite_proofs[:len(arguments.squash)])
        accounted_proofs = dict(rewrite_proofs[len(arguments.squash):])
        plan = plan_retirement(
            repository,
            arguments.destination,
            destination_commit,
            arguments.recovery_prefix.rstrip("/"),
            arguments.worktree,
            branches,
            squash_proofs,
            arguments.drop_ignored,
            accounted_proofs,
        )
        result = plan if arguments.dry_run else apply_retirement(repository, plan)
    except (RetirementRefused, subprocess.CalledProcessError, OSError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            message = error.stderr.strip() or "Git rejected a retirement step"
        else:
            message = str(error)
        print(f"Retirement refused: {message}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
