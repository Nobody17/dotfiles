# Remove integrated local branches

After the assigned integrator exits, acquire the exclusive integration slot for an orchestrator-owned cleanup job. Hold it during the checks and ref deletion so another integration or rewrite cannot change the destination being checked. On resume, reconcile any partially completed cleanup from its recorded refs and ledger entries.

## Establish eligibility

Consider only exact local branch names recorded as created by this run. Preserve base, default, protected, user-owned, and remote branches. A branch still needed by an agent, dependent ticket, open PR, publication, handoff, or recovery operation remains in place.

Confirm that no worktree has the branch checked out and no process or unfinished Git operation uses it. Read its current tip and compare it with the accepted tip in the ledger. If it advanced, preserve it and account for every additional change before reconsidering deletion.

Identify the validated destination: the integration branch for ticket/candidate branches, or the intended target branch for the final integration branch. Verify that the branch's complete work is integrated there:

- **Ancestry:** the exact branch tip is an ancestor of the validated destination SHA.
- **Squash or rebase:** require the recorded starting SHA, submitted-to-integrated commit mapping covering the entire branch range, and accepted review/check evidence for the integrated result. Compare the source and integrated changes, accounting for every difference and any reviewed conflict resolution. Unaccounted commits or changes keep the branch in place; a passing test run alone is insufficient proof.

The final integration branch stays available until its whole change has landed in the intended target and no remaining workflow needs its name. Local ticket integration alone does not satisfy this condition.

## Preserve, then delete

Create a uniquely named run-owned Git recovery ref outside `refs/heads/` at the branch's exact tip, or verify an existing recovery ref points to that same SHA. Record the branch name, tip, validated destination SHA, integration evidence, and recovery ref in the ledger **before deletion**. A SHA written in a report or an expiring reflog is not a substitute for a live ref that keeps the commits reachable.

Recheck branch ownership, worktree use, and the unchanged destination. Delete only the fully qualified branch ref with the expected old SHA:

```bash
git update-ref -d refs/heads/<branch-name> <recorded-tip-sha>
```

An expected-SHA mismatch stops deletion and requires inspection. Verify the branch ref is absent and the recovery ref still resolves to the original tip, then mark its cleanup complete. Preserve the branch and record the reason whenever an eligibility or preservation check is incomplete. Release the slot when the cleanup job finishes or stops, once no ref operation remains in progress.

Retain recovery refs and saved files after branch cleanup. Pruning recovery data is a separate task; this cleanup never removes the only durable reference to the original commits.
