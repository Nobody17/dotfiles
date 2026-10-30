---
name: herdr-pane-mute
description: Mute the Herdr sounds of a worker pane. Use when you create a Herdr pane for a worker agent that you supervise, or to mute, unmute, or check a pane.
---

# Herdr pane mute

A muted pane makes patched Herdr clients skip its completion and needs-input sounds. Toasts, agent status, and terminal bells stay. The mute is a metadata token on the server pane, so it applies to every patched client that views that server. Only Herdr clients built with the local patch of the dotfiles (`mise/.config/mise/herdr-local/`) skip the sounds; other clients still play them.

Read the installed `herdr` skill first and pass its `HERDR_ENV` check. That skill owns the rules for pane creation, agent start, and prompt.

Mute a worker pane that you supervise. Keep a pane audible when the user should hear it directly.

## Start a muted worker

Mute the pane before the worker starts:

1. Create the pane as the `herdr` skill says (a split, or a new tab), and read its pane ID from the response.

2. Mute that pane:

   ```sh
   herdr pane report-metadata <pane_id> --source dotfiles:pane-mute --token dotfiles_pane_mute=1
   ```

   The command prints nothing and exits 0 when the mute is in effect on the server. Any other exit status means the pane is not muted: read the error, correct the cause, and mute again before step 3.

3. Start the worker in that pane and prompt it as the `herdr` skill says (`herdr agent start ... --pane <pane_id>`, then `herdr agent prompt`).

**Limitation:** a client can get a notification before the client snapshot that carries the mute. This occurs when the state of the agent changes within one render interval (normally 16 ms) after the mute. Then the sound still plays. An agent start takes much longer than this interval, so a mute before the start is reliable.

## Mute, unmute, and check

To mute a pane whose worker already runs, use the mute command of step 2. Because of the limitation above, a state change right after the mute can still play one sound.

Unmute a pane when its worker no longer needs your supervision, for example when the user takes it over:

```sh
herdr pane report-metadata <pane_id> --source dotfiles:pane-mute --clear-token dotfiles_pane_mute
```

Unmute restores the normal sound settings. When the user disabled sounds globally or for that agent type, the pane stays silent.

Check the mute state:

```sh
herdr pane get <pane_id>
```

The pane is muted when `.result.pane.tokens` contains `dotfiles_pane_mute`. Herdr omits `tokens` when the pane has no tokens, so a missing field means unmuted.

## Rules

- Use the mute and unmute commands exactly as shown, with no other options. Some other options let Herdr drop a report silently with exit 0, and one ends the mute after a time limit.
- The mute stays through client detach, rename, and move. A move to another workspace gives the pane a new ID; use that ID for later commands.
- The mute ends when the pane closes or the server restarts, including `herdr update --handoff`. After a restart, mute the restored worker panes again.
