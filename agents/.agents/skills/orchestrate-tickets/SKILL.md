---
name: orchestrate-tickets
description: Orchestrate ticketed specs through Herdr with Opus workers, Codex reviews, and a fresh integrator per ticket.
disable-model-invocation: true
---

# Orchestrate tickets

The invoking Claude or Codex session is the **orchestrator**. Execute an existing spec and its tickets through independent Herdr sessions. Final history has one commit per implementation ticket, with ticket reviews before integration and a whole-change review at the end.

## 1. Prepare the run

Read the repository instructions, tracker configuration, spec, and all tickets. Resolve missing references and dependency cycles before dispatch. Use existing tickets from Matt Pocock's spec/ticket workflow; keep their acceptance criteria authoritative.

Read the installed `herdr` skill and satisfy its environment check before controlling panes. Discover commands from the installed CLI. Resolve the installed `codex-review-code` skill and record its absolute path. If either dependency is unavailable, report the missing dependency and pause launch. When the `herdr-pane-mute` skill is installed, mute each pane you create for a delegated agent before that agent starts, as the skill describes.

Use these defaults unless the user supplies an override:

- Ticket workers and integrators: Claude Code, `claude-opus-5-5`, installed effort default.
- Codex reviewers: the configuration selected by `codex-review-code`.
- Concurrency: four ticket workers and one integrator. Review sessions are additional.
- Base branch: the repository's development branch; resolve ambiguity before creating branches.

Check native launch flags with local help. Pin the requested model, inspect the actual model after startup, and report any substitution before assigning work. The orchestrator retains its current harness/model. All delegated work, including nested reviews, uses Herdr sessions.

Pin the base SHA. Create a run-owned integration branch and worktree, preserving unrelated work. Follow repository setup for separate runtime resources such as ports and databases. Record the commands for ticket checks, fast integration checks, and final full validation. Derive them from repository configuration. Give integration checks a concrete time budget, defaulting to 60 seconds total; a check that exceeds it remains incomplete. Resolve mandatory checks that cannot fit the policy before dispatch.

Create a persistent run directory outside tracked source, reachable by absolute path from every worktree. The orchestrator alone writes its ledger. Record:

- Spec/ticket references, pinned base, configuration, validation commands and budgets.
- Integration branch/worktree, last validated SHA, and exclusive integrator owner.
- Per ticket: dependencies, expected edit scope, status, worktree/branch, starting SHA, Herdr IDs, submitted SHA, integrated SHA, and test/review evidence.
- Resource ownership and cleanup status, including reviewers, candidate worktrees, and local branches with their recorded tips created by delegated agents.

Use `pending → working → reviewed → integrating → integrated`, with `blocked` retaining its reason and previous stage. Save complete handoff results in the run directory. Herdr lifecycle states tell you when to inspect results; validate evidence before advancing the ledger. On resume, reconcile the ledger with Git and live sessions first.

**Ready:** every ticket is readable, dependencies resolve, launch settings are known, and the ledger identifies the integration branch and validation policy.

## 2. Dispatch the frontier

The **frontier** contains tickets whose blockers are integrated and have passed integration checks. Start independent frontier tickets up to the worker limit. Serialize overlapping edits, shared migrations, lockfiles, and incompatible interface assumptions. Reassess overlap when workers discover it.

Create each ticket branch/worktree from the latest validated integration SHA. Local ticket references must be absolute paths accessible from that worktree; preserve their linked context. A ticket must provide its acceptance criteria and any needed spec reference. Resolve missing context before launch.

Start a fresh worker in a new Herdr tab at its worktree, preserving user focus. Prepare an assignment file containing its worktree, starting SHA, owned scope, validation commands, and resolved review-skill path. Bootstrap it with the absolute paths to [the worker instructions](references/worker.md) and its assignment file. Wait for acknowledgement, then send **only the ticket file path or URL** as its task message. Pass context pointers, never an orchestrator-written replacement for the ticket.

When invoking a slash skill through Herdr, send the slash command alone, wait for it to load, then send task text separately. Use plain-file role instructions for bootstrap; they do not depend on slash expansion.

Capture the worker's complete handoff under the run directory. Verify its submitted SHA, clean worktree, passing ticket checks, and completed review before queuing it. Keep the worker available for source fixes until integration succeeds; then retire it under the cleanup policy below. Retire completed review sessions once their verdicts are saved.

**Reviewed:** the current submitted tree passes ticket checks and `codex-review-code` reports no open findings for that tree.

## 3. Integrate one ticket at a time

Acquire the exclusive integration slot with atomic directory creation at `<run>/integration.lock`. Record the assigned job and session IDs in it. While occupied, only that integrator changes integration history. Independent ticket workers can continue.

For each queued ticket, start a **fresh** integrator session in its own Herdr tab. Bootstrap it with [the integrator instructions](references/integrator.md) and an assignment containing the lock path, ticket reference, submitted/start SHAs, worker handoff, current integration SHA, worktree paths, and validation policy. Obtain the worker's idle, clean handoff before changing its history. Keep submitted commits reachable through run-owned recovery refs.

After success, verify the reported integration SHA and validation result and save the handoff. End the integrator session. Before releasing the slot, confirm that it and its Git/test processes have exited and the worktrees have no unfinished Git operation. Then update the ledger and frontier. Each subsequent ticket, recovery, or history-rewrite job gets a new session.

After each accepted integration, close its completed worker and integrator resources and remove unused ticket/candidate worktrees and integrated local branches under the cleanup policy. Perform this cleanup during the run, before dispatching replacement workers.

On timeout, inspect the existing owner before taking action. Preserve the lock while ownership or Git state is unresolved. After confirming the old process has exited, transfer the occupied slot to a fresh recovery integrator. It must finish or abort the recorded operation before accepting other work. A timeout or an idle badge alone never releases ownership.

**Integrated:** the branch advanced by exactly one ticket commit, its fast checks passed on the resulting tree, and the integrator has exited.

## 4. Validate the whole change

Once all tickets are integrated and no workers/reviewers are active, acquire the same exclusive slot and launch a fresh finalizer with [the finalization instructions](references/finalize.md). Pass the pinned base, integration tip, ticket-to-commit mapping, handoffs, and full validation commands.

Record its final commit mapping, review result, and full-suite evidence. Apply the same exit and lock-release rules. If it hands back an unfinished rewrite or further repairs, launch a fresh recovery/finalization job with its evidence.

**Complete:** final history verifies one commit per ticket, `codex-review-code` has no open findings for the final range, and full validation passes on the final tree. Report branch/SHA, ticket outcomes, checks, and any unresolved limitations. Locally integrated tickets remain distinct from tracker closure. Perform remote publication, PR changes, or tracker writes only when included in the user's authorized workflow.

## Retire unused resources

Close agents and remove worktrees and integrated local branches as soon as their assignment is complete and nothing still needs them. Cleanup belongs to the orchestrator; persist each complete handoff and its evidence before closing the session.

1. End run-created agents, reviewers, and related processes, then close their Herdr panes and empty run-created tabs. Preserve user-owned or borrowed sessions; release their assignments instead.
2. Verify that each worktree is clean, has no unfinished Git operation or active process, and its work is integrated or preserved through recovery refs. Save needed untracked or ignored files, such as unique reports and local configuration, outside the worktree before removing it through Git. Preserve dirty or unresolved worktrees and record the specific reason they remain.
3. For unused local ticket, candidate, or integration branches, follow [branch cleanup](references/branch-cleanup.md). Delete only branches whose complete changes are verified as integrated and whose exact tips are preserved by recovery refs.
4. Record closed session IDs, removed worktree paths, and deleted branch names with their old SHAs and recovery refs in the ledger. Keep recovery refs, the ledger, and useful evidence independently of live resources.

Keep the shared integration worktree while integration, final validation, or a required handoff still needs it. Remove it after those tasks finish unless the user requested that it remain. Keep the final integration branch as the deliverable until its changes are integrated into the intended target branch and the branch-cleanup checks pass. Apply the same cleanup to finalizer and review resources at the end. If later findings need an agent or worktree that was retired, create a fresh one from the recorded refs.
