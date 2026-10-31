#!/usr/bin/env python3
"""Verify a linear integration range against an explicit ticket-to-commit map."""

import argparse
import json
import subprocess
import sys


def git_output(repository, *arguments):
    result = subprocess.run(
        ["git", "-C", repository, *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def resolve_commit(repository, revision):
    return git_output(
        repository, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"
    )


def verify_history(repository, base, tip, ticket_assignments):
    base_commit = resolve_commit(repository, base)
    tip_commit = resolve_commit(repository, tip)
    git_output(repository, "merge-base", "--is-ancestor", base_commit, tip_commit)

    ticket_commits = {}
    for assignment in ticket_assignments:
        ticket, separator, revision = assignment.partition("=")
        if not separator or not ticket.strip() or not revision.strip():
            raise ValueError(f"Expected ticket-id=commit, received {assignment!r}")
        if ticket in ticket_commits:
            raise ValueError(f"Duplicate ticket: {ticket}")
        ticket_commits[ticket] = resolve_commit(repository, revision)

    if len(set(ticket_commits.values())) != len(ticket_commits):
        raise ValueError("Each ticket must map to a different commit")

    history = git_output(
        repository, "rev-list", "--reverse", "--parents", f"{base_commit}..{tip_commit}"
    ).splitlines()
    previous_commit = base_commit
    actual_commits = []
    for entry in history:
        commit, *parents = entry.split()
        if parents != [previous_commit]:
            raise ValueError("Integration history must be linear with no merge commits")
        actual_commits.append(commit)
        previous_commit = commit

    if set(actual_commits) != set(ticket_commits.values()):
        raise ValueError("Integration range must contain exactly the mapped ticket commits")

    return {"base": base_commit, "tip": tip_commit, "tickets": ticket_commits}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--tip", required=True)
    parser.add_argument("--ticket", action="append", required=True, metavar="ID=COMMIT")
    arguments = parser.parse_args()
    try:
        result = verify_history(
            arguments.repo, arguments.base, arguments.tip, arguments.ticket
        )
    except (ValueError, subprocess.CalledProcessError, OSError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            message = error.stderr.strip() or "Git rejected the requested history range"
        else:
            message = str(error)
        print(f"History verification failed: {message}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
