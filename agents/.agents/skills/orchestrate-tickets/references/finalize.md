# Finalize the integrated change

You own the exclusive integration slot for final review, validation, and the folds that the review needs. Read the assignment and repository instructions. Verify the integration tip and ticket mapping, and confirm every implementation worker, earlier integrator, and reviewer has stopped editing. Send every message for the orchestrator (readiness, questions, blocks, status) as a file, as [messages](messages.md) describes.

## Review and repair

Create a run-owned candidate branch/worktree at the recorded integration tip. Perform review and repairs there, keeping the integration checkout clean. Read and execute the installed `cross-review-code` skill against the complete range from the pinned run base to that tip. Select the committed range deliberately: an empty uncommitted diff does not review the run. Follow its counterchecks, correction loop, and stopping rules, using Herdr for a reviewer of the agent kind in your assignment.

Assign each justified fix to its owning ticket before editing, including test adjustments owned by dependent tickets. Keep fixes scoped to the existing acceptance criteria; report work that needs a new ticket to the orchestrator. In correction rounds, give the reviewer the full base-to-tip range plus the candidate's uncommitted/untracked repairs. Run affected tests and complete the review loop on that repaired tree. Keep review counterchecks restored before preserving changes.

When source fixes have passed review, commit them as ticket-specific fixups on the candidate branch. Preserve both the old integration tip and the repair-commit tip through recovery refs before rewriting. Fold the fixups into their owning ticket commits and replay later commits. Each later round of reviewed fixes folds the same way, with its own recovery refs; the round limit of the review is the only limit. Resolve mechanical replay conflicts; if further source work is needed, return a handoff for a fresh finalizer after completing or aborting the operation. On any earlier stop, retain the candidate worktree, including uncommitted/untracked fixes, and report its path and state.

Record the new ticket-to-commit mapping. Verify each fold mechanically and save the output as evidence:

- The tree of the folded tip equals the tree of the repair-commit tip that the reviewer passed.
- `git range-diff` of the old against the new range shows a changed patch only for the commits that own a fixup.
- The history holds one commit per ticket, with no `fixup!`, `amend!` or `squash!` commit, and with unchanged subjects, authors and author dates.

A fold that passes these checks needs no reviewer round: its content is already reviewed. Ask the reviewer only when the trees differ, which means that a replay conflict was resolved; then give it the resolution. Review evidence must identify the tree of the final tip and have no open findings.

## Validate and publish locally

Run every heavy command (tests, builds) in the `heavy-job.py` form that your assignment gives; exit 124 means the orchestrator stopped the job, and its next message tells you what to do. After the last fold, run the full repository suite at every commit of the final range whose tree has no passing suite run in the evidence yet; a commit whose tree is unchanged keeps its earlier run. Run the other required checks on the final candidate tree. Once they pass, run `scripts/verify-history.py` from this skill with the original base, candidate tip, and one `--ticket <id>=<sha>` for every implementation ticket. Verify a clean worktree.

If no rewrite was needed, validate the existing integration tip the same way. If history changed, update only the run-owned local integration branch after verifying its old SHA still matches the recorded tip. Use a compare-and-swap ref update, with that branch detached from all worktrees during the update, then restore its integration checkout. Preserve unrelated and published history; remote rewriting requires its own existing authorization.

If later validation reveals a needed change, take it through review and fold it as above, then repeat the validation for the changed trees. When your context does not allow that, hand off the evidence and recovery refs; a fresh finalizer continues. Review findings, test failures, and incomplete checks keep the run unfinished.

Write the handoff to the handoff path in your assignment, then reply with that path and a one-line status. The handoff gives the final integration/tree SHAs, complete ticket mapping, reviewer conclusion, full validation results, and recovery refs. Include candidate worktree paths, every run-created branch with its current tip, and reviewer pane/tab IDs with their ownership so the orchestrator can retire them. Confirm there is no unfinished Git operation, then exit when the orchestrator ends the session.
