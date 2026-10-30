# 03: Document the muted worker workflow for agents

Status: needs-info
Blocked by: 01

**What to build:** Agent instructions for the split → mute → run workflow, installed through the repo's existing agent configuration mechanism.

Set to `ready-for-agent` when ticket 01 records the mute command.

- [ ] Instructions show the ordered flow: `herdr pane split` (keeping the existing working-directory and no-focus conventions), mute the returned pane ID, wait for success, then start and prompt the worker.
- [ ] Instructions show how to unmute a pane and how to check its mute state.
- [ ] Instructions state that mute only silences Herdr completion and needs-input sounds. Toasts, agent status, and terminal bells stay. Mute needs the patched client from ticket 02.
- [ ] Instructions live in a repo-owned file, not in an upstream-managed integration that a reinstall would overwrite.
