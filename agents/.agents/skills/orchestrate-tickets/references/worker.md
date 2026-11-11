# Ticket worker

Read your assignment file and repository instructions, verify the assigned worktree and starting SHA, then send a `ready` message. Send every message for the orchestrator (readiness, questions, blocks, status) as a file, as [messages](messages.md) describes. Your next task message is the ticket file path or URL. Read that ticket and its linked context directly.

## Implement and validate

Implement the ticket's acceptance criteria within its assigned scope. Run relevant ticket tests and affected checks until they pass. Run every heavy command (tests, builds) in the `heavy-job.py` form that your assignment gives; exit 124 means the orchestrator stopped the job, and its next message tells you what to do. Reserve the full repository suite for final integration validation. If repository-required checks conflict with this policy, report the conflict to the orchestrator instead of silently omitting them. Record each manual check with the log file that shows its result, in the ticket and in the handoff; mark a statement that no log shows as reported.

Dependencies already integrated into your starting commit are part of your test environment. Report newly discovered dependencies or edit overlap before crossing another ticket's scope. The orchestrator owns scheduling; the integrator owns rebases, squashes, cherry-picks, and integration-branch changes. Request synchronization when needed and wait for the assigned integrator.

## Review the ticket

Read and execute the assigned `cross-review-code` skill in this worktree. Follow its counterchecks, review rounds, correction loop, and stopping rules. Keep the review scoped to this ticket's changes since its starting SHA, including uncommitted and untracked work. If implementation commits exist, an uncommitted-only review is insufficient: cover the complete ticket diff.

The reviewer is the agent kind in your assignment. Reviewers inspect without editing. Use Herdr for their sessions. When reusing a reviewer, verify both its target worktree and exclusive availability. A reviewer already assigned elsewhere stays with that assignment.

After a correction, rerun affected ticket checks and the review's required counterchecks. A review with open findings, an incomplete response, or an exhausted round limit is a blocked handoff. Return the evidence to the orchestrator; keep other tickets independent of that decision.

## Submit

After review succeeds, commit the reviewed work with ticket identity in the message and leave the worktree clean. Any earlier implementation commits remain available for the integrator to squash. Code changes after review require another review round; committing an unchanged reviewed tree preserves its evidence.

Write a concise handoff to the handoff path in your assignment. A later handoff for the same ticket, after a fix, goes to a numbered file next to it (`-2`, `-3`). The handoff contains:

- Ticket reference, starting SHA, submitted SHA, and tree SHA.
- Changed scope and acceptance-criteria results.
- Test commands/results, including failures or skips.
- Reviewer identity and pane/tab IDs, whether the session was created or borrowed, reviewed scope/tree, and its explicit final finding status.
- Remaining risks and any repository-required changelog text.

Then end your reply with the handoff path and a one-line status. Remain available for source fixes until integration succeeds, then let the orchestrator close your session and remove the unused worktree. Report completed review sessions for cleanup once their verdicts are captured. History operations stay with the integrator.

**Done:** the submitted tree is clean, ticket checks pass, and a complete review confirms no open findings for that tree.
