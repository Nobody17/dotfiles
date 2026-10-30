# 03: Document the muted worker workflow for agents

Status: ready-for-agent
Blocked by: 01

**What to build:** Agent instructions for the split → mute → run workflow, installed through the repo's existing agent configuration mechanism.

**Commands (ticket 01):**

```sh
# mute
herdr pane report-metadata <pane_id> --source dotfiles:pane-mute --token dotfiles_pane_mute=1
# unmute
herdr pane report-metadata <pane_id> --source dotfiles:pane-mute --clear-token dotfiles_pane_mute
# check: the pane is muted when "tokens" contains "dotfiles_pane_mute"
herdr pane get <pane_id>
```

The mute command prints nothing and exits 0 on success. Do not add `--seq`, `--ttl-ms`, `--agent`, or `--applies-to-source`: with some of them a report can be dropped silently with exit 0, and a TTL ends the mute. `pane get` omits the `tokens` field when the pane has no tokens.

**Limitation (ticket 01, Decision):** mute the pane before the worker starts. A state change that comes within one render interval of the mute (normally 16 ms) can still play a sound. Mute is lost on pane close and on server restart, including `herdr update --handoff` (from the source; not tested).

- [x] Instructions show the ordered flow: `herdr pane split` (keeping the existing working-directory and no-focus conventions), mute the returned pane ID, wait for success, then start and prompt the worker.
- [x] Instructions show how to unmute a pane and how to check its mute state.
- [x] Instructions state that mute only silences Herdr completion and needs-input sounds. Toasts, agent status, and terminal bells stay. Mute needs the patched client from ticket 02.
- [x] Instructions state the limitation: mute before the worker starts; the race window is one render interval.
- [x] Instructions live in a repo-owned file, not in an upstream-managed integration that a reinstall would overwrite.
