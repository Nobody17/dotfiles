# Finalize the integrated change

You own the exclusive integration slot for final review, validation, and at most one history-rewrite job. Read the assignment and repository instructions. Verify the integration tip and ticket mapping, and confirm every implementation worker, earlier integrator, and reviewer has stopped editing.

## Review and repair

Create a run-owned candidate branch/worktree at the recorded integration tip. Perform review and repairs there, keeping the integration checkout clean. Read and execute the installed `codex-review-code` skill against the complete range from the pinned run base to that tip. Select the committed range deliberately: an empty uncommitted diff does not review the run. Follow its counterchecks, correction loop, and stopping rules, using Herdr for the Codex reviewer.

Assign each justified fix to its owning ticket before editing, including test adjustments owned by dependent tickets. Keep fixes scoped to the existing acceptance criteria; report work that needs a new ticket to the orchestrator. In correction rounds, give the reviewer the full base-to-tip range plus the candidate's uncommitted/untracked repairs. Run affected tests and complete the review loop on that repaired tree. Keep review counterchecks restored before preserving changes.

When source fixes have passed review, commit them as ticket-specific fixups on the candidate branch. Preserve both the old integration tip and the repair-commit tip through recovery refs before rewriting. Fold the fixups into their owning ticket commits and replay later commits in a single rewrite job. Resolve mechanical replay conflicts; if further source work is needed, return a handoff for a fresh finalizer after completing or aborting the operation. On any earlier stop, retain the candidate worktree, including uncommitted/untracked fixes, and report its path and state.

Record the new ticket-to-commit mapping. Ask the reviewer to verify the final candidate range and any replay resolutions; review evidence must identify the final tree and have no open findings.

## Validate and publish locally

Run the full repository suite and required checks on the final candidate tree. Once they pass, run `scripts/verify-history.py` from this skill with the original base, candidate tip, and one `--ticket <id>=<sha>` for every implementation ticket. Verify a clean worktree.

If no rewrite was needed, validate the existing integration tip the same way. If history changed, update only the run-owned local integration branch after verifying its old SHA still matches the recorded tip. Use a compare-and-swap ref update, with that branch detached from all worktrees during the update, then restore its integration checkout. Preserve unrelated and published history; remote rewriting requires its own existing authorization.

If later validation reveals changes requiring another rewrite, hand off the evidence and recovery refs. A fresh finalizer takes the next rewrite job. Review findings, test failures, and incomplete checks keep the run unfinished.

Return the final integration/tree SHAs, complete ticket mapping, reviewer conclusion, full validation results, and recovery refs. Include candidate worktree paths, every run-created branch with its current tip, and reviewer pane/tab IDs with their ownership so the orchestrator can retire them. Confirm there is no unfinished Git operation, then exit when the orchestrator ends the session.
