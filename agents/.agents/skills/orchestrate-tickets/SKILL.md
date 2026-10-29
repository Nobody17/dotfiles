---
name: orchestrate-tickets
description: Orchestrate ticketed specs through Herdr with Opus workers, Codex reviews, and a fresh integrator per ticket.
disable-model-invocation: true
---

# Orchestrate tickets

The invoking Claude or Codex session is the **orchestrator**. Execute an existing spec and its tickets through independent Herdr sessions. Final history has one commit per implementation ticket, with ticket reviews before integration and a whole-change review at the end.

## 1. Prepare the run

Read the repository instructions, tracker configuration, spec, and all tickets. Resolve missing references and dependency cycles before dispatch. Use existing tickets from Matt Pocock's spec/ticket workflow; keep their acceptance criteria authoritative.

Read the installed `herdr` skill and satisfy its environment check before controlling panes. Discover commands from the installed CLI. Resolve the installed `codex-review-code` skill and record its absolute path. If either dependency is unavailable, report the missing dependency and pause launch.

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

Use `pending → working → reviewed → integrating → integrated`, with `blocked` retaining its reason and previous stage. Save complete handoff results in the run directory. Herdr lifecycle states tell you when to inspect results; validate evidence before advancing the ledger. On resume, reconcile the ledger with Git and live sessions first.

**Ready:** every ticket is readable, dependencies resolve, launch settings are known, and the ledger identifies the integration branch and validation policy.

## 2. Dispatch the frontier

The **frontier** contains tickets whose blockers are integrated and have passed integration checks. Start independent frontier tickets up to the worker limit. Serialize overlapping edits, shared migrations, lockfiles, and incompatible interface assumptions. Reassess overlap when workers discover it.

Create each ticket branch/worktree from the latest validated integration SHA. Local ticket references must be absolute paths accessible from that worktree; preserve their linked context. A ticket must provide its acceptance criteria and any needed spec reference. Resolve missing context before launch.

Start a fresh worker in a new Herdr tab at its worktree, preserving user focus. Prepare an assignment file containing its worktree, starting SHA, owned scope, validation commands, and resolved review-skill path. Bootstrap it with the absolute paths to [the worker instructions](references/worker.md) and its assignment file. Wait for acknowledgement, then send **only the ticket file path or URL** as its task message. Pass context pointers, never an orchestrator-written replacement for the ticket.

When invoking a slash skill through Herdr, send the slash command alone, wait for it to load, then send task text separately. Use plain-file role instructions for bootstrap; they do not depend on slash expansion.

Capture the worker's complete handoff under the run directory. Verify its submitted SHA, clean worktree, passing ticket checks, and completed review before queuing it. A worker stays assigned to its ticket for requested fixes, then remains idle.

**Reviewed:** the current submitted tree passes ticket checks and `codex-review-code` reports no open findings for that tree.

## 3. Integrate one ticket at a time

Acquire the exclusive integration slot with atomic directory creation at `<run>/integration.lock`. Record the assigned job and session IDs in it. While occupied, only that integrator changes integration history. Independent ticket workers can continue.

For each queued ticket, start a **fresh** integrator session in its own Herdr tab. Bootstrap it with [the integrator instructions](references/integrator.md) and an assignment containing the lock path, ticket reference, submitted/start SHAs, worker handoff, current integration SHA, worktree paths, and validation policy. Obtain the worker's idle, clean handoff before changing its history. Keep submitted commits reachable through run-owned recovery refs.

After success, verify the reported integration SHA and validation result, then update the ledger and frontier. Before releasing the slot, confirm that the integrator and its Git/test processes have exited and the worktrees have no unfinished Git operation. Each subsequent ticket, recovery, or history-rewrite job gets a new session.

On timeout, inspect the existing owner before taking action. Preserve the lock while ownership or Git state is unresolved. After confirming the old process has exited, transfer the occupied slot to a fresh recovery integrator. It must finish or abort the recorded operation before accepting other work. A timeout or an idle badge alone never releases ownership.

**Integrated:** the branch advanced by exactly one ticket commit, its fast checks passed on the resulting tree, and the integrator has exited.

## 4. Validate the whole change

Once all tickets are integrated and all workers/reviewers are idle, acquire the same exclusive slot and launch a fresh finalizer with [the finalization instructions](references/finalize.md). Pass the pinned base, integration tip, ticket-to-commit mapping, handoffs, and full validation commands.

Record its final commit mapping, review result, and full-suite evidence. Apply the same exit and lock-release rules. If it hands back an unfinished rewrite or further repairs, launch a fresh recovery/finalization job with its evidence.

**Complete:** final history verifies one commit per ticket, `codex-review-code` has no open findings for the final range, and full validation passes on the final tree. Report branch/SHA, ticket outcomes, checks, and any unresolved limitations. Locally integrated tickets remain distinct from tracker closure. Perform remote publication, PR changes, or tracker writes only when included in the user's authorized workflow.

Retain the integration worktree, ledger, and useful evidence for handoff. Remove only run-created resources whose work is preserved and whose processes have exited.
