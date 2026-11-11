# Assignment: ticket {{ticket_id}} worker ({{ticket.agent_name}})

Run: {{run}} (the ledger is orchestrator-owned; do not edit it)

## Ticket and context
- Ticket: {{ticket.file}} (sent as your task message after your `ready`)
- Spec: {{ledger.spec}}
- Repository instructions: the agent instruction files in your worktree.

## Worktree
- Path: {{ticket.worktree}}
- Branch: {{ticket.branch}}
- Starting SHA: {{ticket.start_sha}}
- Stay in this worktree. Other worktrees and the integration branch belong to other jobs.

## Owned scope
{{ticket.scope}}

Shared interfaces (owner → consumers): {{ledger.shared_interfaces}}
Report newly found overlap with another ticket as a `question` message before you cross it.

## Validation
Every heavy command (tests, builds) runs through the wrapper; the run has {{ledger.heavy_jobs.slots}} slot(s), so the wrapper can wait.
- Tests: `{{ledger.validation.test_command}}`
- Ticket checks: {{ledger.validation.ticket_checks}}
- The full suite belongs to the finalizer.
- Keep at least {{ledger.config.min_free_disk_gb}} GB free disk; send a `blocked` message below that.

## Review
- Skill: {{ledger.config.review_skill}} (absolute path; read and execute it).
- Reviewer: {{ledger.config.reviewer}}, a fresh session in a new muted Herdr tab (`--no-focus`) of workspace {{ledger.config.herdr_workspace}}, named `{{ticket.agent_name}}-rev`, cwd = your worktree.
- Review scope: everything since {{ticket.start_sha}}, committed and uncommitted.
- The run has a form for heavy commands, so the reviewer only reads.

## Commit and handoff
- One commit with the ticket ID in its message.
- Write the handoff to {{ticket.handoff}} (later fixes: -2, -3 next to it).
- Leave the reviewer session open and name its pane and tab IDs in the handoff; the orchestrator retires it.
