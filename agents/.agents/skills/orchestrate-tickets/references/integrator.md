# Ticket integrator

You own one integration or recovery job. Read the assignment, repository instructions, and the installed Herdr skill. Confirm that the exclusive lock records your assignment and that the pinned integration tip still matches Git. Your session exits after this job; the orchestrator releases the slot.

## Prepare the candidate

Verify the submitted/start SHAs, ticket scope, clean idle worker handoff, passing ticket checks, and completed review. Return incomplete submissions with an actionable request. Preserve the submitted commit through the assigned recovery ref.

In a run-owned candidate worktree, consolidate only this ticket's changes since its recorded starting SHA into one commit, then rebase that candidate onto the current integration tip. Include required changelog changes in that ticket commit. The integration branch stays at its validated tip while the candidate is prepared.

Resolve mechanical conflicts using the ticket and current interfaces. A conflict that needs a product decision or changes ticket behavior returns to the orchestrator for a scoped source fix. Finish or abort the current rebase before handing back ownership.

If conflict resolution or other edits change the reviewed implementation, rerun affected ticket tests and `codex-review-code` on the changed ticket candidate. Follow that skill's correction and stopping rules. An unchanged patch rebased without conflict needs the fast integration checks; record that its ticket review predates integration rather than claiming the combined tree was fully reviewed.

## Validate and advance

Run the assignment's fast, relevant checks against the combined candidate tree within the recorded total time budget. A timeout, skipped required check, or failed check blocks advancement. Return failures for a scoped fix; reserve the full suite for finalization. A deliberate test countercheck fails as expected and is recorded separately from the required passing checks.

Use the bundled history verifier before advancing:

```bash
python3 <skill>/scripts/verify-history.py --repo <candidate-worktree> \
  --base <current-integration-sha> --tip <candidate-sha> \
  --ticket <ticket-id>=<candidate-sha>
```

This verifies one linear commit above the assigned tip. Verify the candidate worktree is clean and the integration tip is unchanged, then fast-forward integration to that exact candidate. The checks ran on the resulting tree before moving the branch; a separate identical post-merge run adds no evidence. If the tip changed, stop and report the ownership mismatch.

Return ticket ID, submitted-to-integrated SHA mapping, resulting integration/tree SHAs, check commands/results, review evidence if renewed, and recovery refs. Include candidate worktree paths, every run-created branch with its current tip, and reviewer pane/tab IDs with their ownership so the orchestrator can retire them. Confirm no Git operation remains in progress, then exit when the orchestrator ends the session.

## Recover an interrupted job

Read the previous owner's handoff, lock ownership, recovery refs, and actual Git state before acting. Reconcile a possibly completed fast-forward before retrying it. If integration already equals the recorded candidate, rerun missing fast checks and report the recovered mapping instead of applying the ticket again. Complete or abort any interrupted operation, preserve source work, and report the resulting state. Treat missing validation evidence as incomplete. The orchestrator assigns the next job to a fresh session.
