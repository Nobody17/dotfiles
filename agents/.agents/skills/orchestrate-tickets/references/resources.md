# Shared resources of a run

Parallel agents share the machine: memory (often a container VM with its own limit), CPU, and disk. A **heavy job** is one command that loads them for minutes: a test run, a build, a browser test session. When memory runs out, the kernel kills a process, and a test runner with forked workers can then wait forever for the dead one. Two guards prevent this, and the watcher detects what gets past them:

- **Slots:** every heavy job of the run takes one of N slots through [`scripts/heavy-job.py`](../scripts/heavy-job.py), so at most N run at the same time.
- **Review time:** when a job runs longer than its review time, the same script marks it overdue. The job continues; only a reviewer's decision stops it.
- **Alarms:** [`scripts/watch-run.py`](../scripts/watch-run.py) reports overdue jobs, low memory or disk, new kernel OOM kills, and resting agents that still have running shells.

## Size the slots before dispatch

Measure; record the numbers and how you got them in `ledger.heavy_jobs.sizing`.

1. **Pool:** the memory limit that the jobs share, such as the container VM total or the host memory.
2. **Resident load:** what stays in the pool while no job runs, for every runtime stack you will start. One stack per worktree multiplies it by the number of live worktrees: ticket workers, the integration worktree, candidate worktrees.
3. **Job peak:** the peak memory of one heavy job with the run's test settings (for example 2 parallel test processes). Read `memory_peak_mb` of comparable jobs in `<run>/heavy-jobs/history.jsonl` of this or an earlier run; `heavy-job.py` writes it when `heavy_jobs.memory_probe` is set. Without a history, measure one typical ticket test run through the wrapper before dispatch.
4. **Slots** = (pool − resident load − 20 % reserve) ÷ job peak, rounded down, at least 1. When the result is below 1, reduce the worker limit: fewer worktrees mean less resident load.
5. **Review time:** about 1.5 × the longest `run_seconds` of a ticket or fast-check job in the history. An early review costs one look; a late one lets a hang hold its slot. A full-suite run gets its own `--review-after-minutes` in the finalizer's command.

Re-measure when the number of live stacks or the test settings change, and lower the slots or the worker limit when an alarm shows pressure. A high `waited_seconds` in the history with memory to spare is the signal to add a slot.

Sessions outside the run share the pool and take no slot. Before you size, list them (`herdr agent list`) and ask the user which of them run tests during the run; leave their stacks running.

## Record the policy

```json
"heavy_jobs": {
  "slots": 1,
  "review_after_minutes": 10,
  "lock": "<run>/heavy-job.lock",
  "stop_cleanup": "<command that stops what the stopped client leaves behind>",
  "memory_probe": "<prints the available MB of the pool>",
  "sizing": "pool 7.7 GB; 4 stacks resident 4.1 GB; job peak 1.6 GB; reserve 1.5 GB -> 1 slot"
},
"resource_watch": {
  "every_minutes": 2,
  "idle_shell_minutes": 30,
  "checks": [
    {"name": "disk-gb", "command": "df -g <run> | awk 'NR==2 {print $4}'", "minimum": 8},
    {"name": "pool-memory-mb", "command": "<prints available MB>", "minimum": 1200},
    {"name": "oom", "command": "<prints the kernel log>", "match": "Killed process"},
    {"name": "base", "command": "<prints 'base moved: <sha>' when the base branch left the pinned SHA>", "match": "base moved"}
  ]
}
```

`heavy-job.py` and `watch-run.py` read these keys from `<run>/ledger.json`; their `--help` gives the details. The watcher reads `resource_watch` again before each check round, so a ledger change applies without a restart.

`stop_cleanup` runs in the job's directory after a `--stop`. It is necessary when the job's client is not the process that does the work: stopping `docker compose exec` leaves the test processes running in the container. For such a stack, restart the service or kill the processes inside it.

Example values for one Docker Desktop VM: pool memory `docker run --rm alpine:3 awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo`, kernel log `docker run --rm --privileged alpine:3 dmesg`, cleanup `bin/worktree compose restart web`.

## Put the wrapper in each assignment

Write every heavy command of the assignment, for each role, in this form:

```text
python3 <skill>/scripts/heavy-job.py --run <run> --label <ticket>-<purpose> -- <command> <arguments>
```

Agents append their files to `<arguments>`. The command runs without a shell; wrap a command that needs one as `-- sh -c '<command>'`.

Reviewers are heavy-job sources too: one reviewer ran the full suite with 8 workers in a worker's stack and caused OOM kills. With this form in the assignment, `cross-review-code` tells the reviewer to ask for runs instead, and the assigned agent runs them in this form. The rule is an instruction, not a lock: a reviewer's own run still shows in its answer and in the memory alarms.

## Review an overdue job

`job <job> <label> needs a review` means the job passed its review time and still runs. Review it before you handle other events; it holds a slot while it waits.

1. Collect the evidence: `heavy-job.py --run <run> --list` gives run time, minutes since the last output, the log path, and the job's processes with their state and memory. Read the end of the log. Look for OOM alarms since the job started.
2. Decide what the evidence shows:
   - **Progress:** the log grows, or its processes use CPU. Extend: `--extend <job> --minutes <M>` with M from the remaining work.
   - **Hang:** the output stopped, an OOM kill hit the job, or a child process shows `Z` (it ended and nobody collected it). Stop: `--stop <job> --reason <text>`; the job's cleanup runs, and its agent sees exit 124 and the reason.
   - **Fixable cause:** for example, another stack fills the memory. Fix the cause, then extend or stop.
3. Record the evidence and the decision in the ledger, then run it.
4. After a stop, tell the owning agent what you found and whether it runs the job again; lower `heavy_jobs.slots` when memory caused the hang.

When the evidence needs the job's context, prompt its owning agent for a diagnosis in a `status` message, and decide after you read it.

## React to other alarms

The watcher reports facts; the orchestrator decides. Record each decision in the ledger before you act.

- `resource <memory or disk check> … below …`: lower `heavy_jobs.slots`, pause dispatch, or retire finished worktrees and their stacks. Running jobs keep their slots until they end.
- `resource base new: base moved: <sha>`: the base branch got commits from outside the run. Tell the user, name the files that those commits share with the run's tickets, and have the finalizer rebase the ticket commits onto the new tip before the whole-change review. After the decision, set the new SHA in the check command.
- `resource oom new: …`: find the job whose process was killed, from the log line and `heavy-job.py --list`, and review that job now.
- `agent <name> … with <K> shells`: read its last reply with `last-reply.py`, then the pane. A shell outside the wrapper gets no review time: tell the agent to stop it and to use the wrapper.
- `job … left by ended wrapper`: nothing watches the job now. Inspect its process group; stop it and run the cleanup command, or let it finish. Tell the owning agent, then delete its record in `<run>/heavy-jobs/`.
- `job … cleanup failed`: the job is stopped, but what it left behind can still use memory; its slot stays held. Clean up by hand, then `--release <job>`; or fix the cause and `--stop <job>` again to rerun the cleanup.
