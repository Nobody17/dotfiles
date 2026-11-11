# Assignment: integrate ticket {{ticket_id}} ({{agent_name}}, job {{job_id}})

Run: {{run}} (the ledger is orchestrator-owned; do not edit it)

## Lock
- Lock directory: {{ledger.integration.lock}} (its owner file names job {{job_id}} and your agent name). The orchestrator releases it.

## Ticket
- Ticket: {{ticket.file}}; spec: {{ledger.spec}}
- Worker handoff: {{ticket.handoff_current}}
- Worker branch/worktree: {{ticket.branch}} at {{ticket.worktree}}
- Starting SHA: {{ticket.start_sha}}; submitted SHA: {{ticket.submitted_sha}}
- Recovery ref to create for the submitted commit: {{ledger.config.recovery_prefix}}/{{ticket.branch}}

## Integration
- Branch: {{ledger.integration.branch}}
- Worktree (checks run here): {{ledger.integration.worktree}}
- Current integration SHA (pinned): {{integration_sha}}
- Candidate: build the single ticket commit in the ticket worktree on the new branch `{{ticket.candidate_branch}}`, based on {{integration_sha}}. Check it out detached in the integration worktree for the fast checks; fast-forward the integration branch only after the checks pass on the identical tree.
- Conflicts: keep the logic of each ticket. A conflict that changes behaviour goes back as a `question`.
- Fast checks: {{ledger.validation.integration_fast_checks}}; total budget {{ledger.validation.integration_budget_seconds}} s.
- Test command: `{{ledger.validation.test_command}}`
- Reviewer for a renewed review: skill {{ledger.config.review_skill}}, session named `{{agent_name}}-rev` in a new muted tab (`--no-focus`) of workspace {{ledger.config.herdr_workspace}}; it only reads.

## Handoff
- Write it to {{run}}/handoffs/{{job_id}}.md, then reply with the path.
