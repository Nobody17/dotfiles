# 01: Spike — can pane metadata carry mute?

Status: resolved
Type: research
Blocked by: none

Time limit: half a day. The result is an answer under `## Answer`, not production code.

**Question:** Can a `report-metadata` token on a pane serve as the pane mute flag that the client checks before it plays a sound?

Answer each point with evidence from the Herdr 0.9.5 source and from a test against an isolated Herdr server (never the user's live server):

- [x] The exact command that sets and clears the token, and what `--source`, `--applies-to-source`, `--seq`, and `--ttl-ms` require.
- [x] A uniquely prefixed token name (proposal: `dotfiles_pane_mute`) is valid under Herdr's token key rules. Tokens share one flat map by name, so search the Herdr source and the agent integrations in this repo for writers of the same name.
- [x] Without `--ttl-ms`, the token stays until it is cleared.
- [x] The token is in effect on the server when the command returns.
- [x] Attached clients receive the token in their pane state. If they do not, a client can read it through the existing API at sound time.
- [ ] Delivery order: after the mute command returns, can a notification for that pane reach the client sound decision before the snapshot with the new token? Answer from the source and with a test on an isolated server. If yes, the client must query the pane through the existing API at sound time; record that for ticket 02. **Failed: yes, it can; and the client connection cannot query the pane through the existing API. See Answer, point 6. The user chose option D (see Decision).**
- [x] The token survives client detach and reopen, stays on the pane after move and rename, and goes away on pane close and on full server restart, including restored panes.
- [x] `herdr pane get` / `pane list` show the token.
- [x] Where the client decides to play completion and needs-input sounds, and how small the patch at that point would be.

**Outcome:** If every point passes, update ticket 02 with the exact command and patch location and set it to `ready-for-agent`. If a point fails, stop and report to the user with the failed point and the options. Do not fall back to a client-local store without a user decision.

## Answer

**Result:** Points 1–5 and 7–9 pass. Point 6 fails: a notification can reach the client before the snapshot with the token, and the client cannot ask the server for the pane through its own connection, because `pane.get` is not allowed there. The user chose option D (see Decision at the end). Tickets 02 and 03 are updated for it.

**Evidence.** Source: Herdr v0.9.5 tag tarball (`github.com/herdrdev/herdr/archive/refs/tags/v0.9.5.tar.gz`, sha256 `a2486b09…52de`). Source paths below are relative to its root. Tests: the installed `herdr 0.9.5` binary against an isolated server (own `HOME`, own `HERDR_SOCKET_PATH`, all live `HERDR_*` variables removed). Raw evidence is in `~/.local/state/orchestrate-tickets/herdr-pane-mute-20261030/evidence/t01/`:

- `iso.sh`: the isolated wrapper
- `transcript-01-command.txt`: command, key rules, TTL, seq
- `transcript-02-lifecycle.txt`: rename, move, detach, close, restart
- `transcript-03-order.txt`: delivery order
- `transcript-04-endpoint-lookup.txt`: API through the client connection
- `scripts/`: the two protocol probes

The auto-mode permission classifier blocked a build of the Herdr source (it runs downloaded build scripts). So no in-process Herdr test ran. The order test uses a Python probe that speaks the 0.9.5 client protocol to the isolated server instead.

### 1. Command

```sh
# mute
herdr pane report-metadata <pane_id> --source dotfiles:pane-mute --token dotfiles_pane_mute=1
# unmute
herdr pane report-metadata <pane_id> --source dotfiles:pane-mute --clear-token dotfiles_pane_mute
```

On success the command prints nothing and exits 0. A server error prints JSON on stderr and exits 1, for example `pane_not_found`. A usage error exits 2, except an invalid number for `--seq` or `--ttl-ms`, which exits 1 (`src/cli/pane.rs:1481-1670`, `src/cli.rs:755-767`).

- `--source` is required. It is 1–80 characters, using ASCII letters, digits, `:`, `.`, `_`, `-` (`src/app/api_helpers.rs:210-227`). It does not put token names in separate namespaces: any source can clear the token (transcript 01, "another source can clear"). Use a source that is not `herdr:<agent>`. For an official agent source whose agent process exited a short time ago, a report is dropped silently with exit 0 (`src/terminal/metadata.rs:79-94`).
- `--applies-to-source` and `--agent`: do not use them. The token patch does not check them as guards (transcript 01). But they bind the report to an agent: the exited-agent drop above can then occur, and the sequence state of the source is reset when that agent exits (`src/terminal/metadata.rs:61-76,118-120`, `src/terminal/state.rs:593-607`).
- `--seq`: do not use it. A report with a seq that is not greater than the last seq for that source is dropped silently with exit 0 (`src/app/api/panes.rs:1803-1830`, `src/metadata_tokens.rs:17-23`). Transcript 01 shows this: set with seq 10, then clear with seq 5, and the token stays. A report without `--seq` is always applied.
- `--ttl-ms`: do not use it. The allowed range is 1–86 400 000. A token with a TTL is removed when the TTL ends (`src/app/api_helpers.rs:229-242`; transcript 01: a 1500 ms token was gone after 4 s, and the mute token stayed).
- The value is trimmed, control characters are removed, and it is cut to 80 characters. An empty value clears the token, so `--token dotfiles_pane_mute=` also unmutes (`src/app/api_helpers.rs:244-277`; transcript 01). Clearing is idempotent. A pane can have at most 32 tokens. Above this limit the report fails with `metadata_token_limit` and exit 1, so it is not silent (`src/app/api/panes.rs:1811-1822`).

### 2. Name and other writers

The key rule is 1–32 characters of ASCII letters, digits, `_`, `-` (`src/app/api_helpers.rs:258-266`). `dotfiles_pane_mute` (18 characters) is valid. `dotfiles.pane.mute` and a 33-character name are rejected (transcript 01). Search for writers of the same name:

- The Herdr source has no match for `dotfiles_`, `pane_mute`, or `mute` tokens. No built-in integration asset (`src/integration/assets/*`) writes tokens. The only `--token` writer in the source is `scripts/seed_navigator_demo.sh` (`summary=`).
- In this repository, the only matches are the spec, the tickets, and ADR 0002.
- The installed Herdr hooks (`~/.claude/hooks/herdr-agent-state.sh`, `~/.codex/herdr-agent-state.sh`, `~/.pi/agent/extensions/herdr-agent-state.ts`) call only `pane.report_agent` and `pane.report_agent_session`. They write no metadata.

### 3. Lifetime without TTL

A token without TTL has `expires_at: None`, and `expire_at` keeps it (`src/metadata_tokens.rs:44-104`). Nothing else removes tokens from a live terminal: the only write paths are `patch` and `expire_at`. The isolated test set the token at 12:01:37 and still read it at 12:03:27, after rename, two moves, and two client attaches (transcript 02).

### 4. In effect when the command returns

The API handler applies the token patch synchronously, before it encodes the success response (`src/app/api/panes.rs:1839-1870`). The CLI waits for that response. A `pane get` right after the command shows the token (transcript 01). The server is in effect at return. Attached clients are not (see point 6). With the command from point 1, none of the silent exit-0 drop paths can occur.

### 5. Clients receive the token

The client snapshot carries tokens only in `ClientShellAgent.tokens`, which the server fills from the terminal's tokens (`src/protocol/wire.rs:1070-1086`, `src/server/client_shell.rs:151-176`). `ClientShellPane` has no tokens (`src/protocol/wire.rs:1058-1067`). So a client sees the token only while the pane has an agent. Semantic agent notifications require an agent label (`src/server/headless/notifications.rs:67-69`), so a pane with a sound normally has an agent entry. But if the agent is released (`pane release-agent`) before the next snapshot, that snapshot has no entry for the pane and so does not show the token, although the token stays on the terminal (`src/terminal/state.rs:1851-1858`, `src/app/agents.rs:378-380`). A missing agent entry does not mean "unmuted". The order probe decodes the snapshots and sees `dotfiles_pane_mute` in the pane's agent entry (transcript 03, `"muted": true`).

### 6. Delivery order — FAILED

**Answer: yes.** The server sends `SemanticNotification` at once, when it handles the state change (`send_to_client_shells`, `src/server/headless.rs:1616-1645`). It sends client snapshots only in the render step. Normally this step runs at most once per 16 ms (`MIN_RENDER_INTERVAL`, `src/app/mod.rs:39`), but presentation and interactive renders can run sooner (`src/server/headless.rs:543-553`, `src/server/headless/render.rs:11-24`). See loop steps 2, 3, and 7 in `src/server/headless.rs:466-560` and the snapshot send in `src/server/headless/render.rs:635-727`. Both use the same ordered control channel. When the render step is not due after the mute, a state change that the server handles before the next render reaches the client first.

Test on the isolated server (`scripts/order_probe.py`, 10 trials for each of three transitions per row: Working→Blocked, Working→Idle, Idle→Working→Idle; simulated agent through `report-agent`, no model, no audible client):

| Mute then state change | Notification before the token snapshot |
| --- | --- |
| direct API, render more than 16 ms ago | 0/30 |
| direct API, render just before the mute | 29/30 (client snapshot at arrival: unmuted) |
| two `herdr` CLI processes, either case | 0/60 (process start takes longer than 16 ms) |

In all 29 early cases, a snapshot with the token followed in the same trial.

Effect on the sound decision (`src/client/shell/notification_policy.rs`). A pending notification waits `ui.toast.delay_seconds` (default 1, `src/config/model.rs:1253`) and, if that is greater than 0, is checked against the snapshot (line 135). A Finished notification that arrives while the snapshot shows Working waits for a newer snapshot (lines 319-370). The check compares the agent status only, not the snapshot revision (lines 347-369). Thus a snapshot from before the mute decides the sound, for example:

- a needs-input notification when `delay_seconds = 0` (no check);
- a needs-input notification when the older snapshot already shows Blocked at the deadline (for example Blocked → mute → Working → Blocked inside one render interval, and the newer snapshot arrives after the deadline);
- a Finished notification when the older snapshot already shows Done from an earlier turn.

So a patch that reads only the snapshot does not guarantee user story 2.

**Why the specified remedy does not work as written:** the client cannot query the pane over its own connection. The server accepts endpoint requests from a client only for the methods in `CLIENT_SHELL_METHODS` (`src/server/client_commands.rs:15-56`, checked in `src/server/client_transport.rs:97-105`). `pane.get`, `pane.list`, and `agent.get` are not in the list. Transcript 04: all three return `unsupported_method`. The JSON API socket (`herdr pane get`) works only when the server runs on the same computer as the client. A client attached through `--remote` or a saved SSH machine has no local API socket to that server.

**Options (the user decides):**

- **A — local API socket lookup.** At sound time the client reads `pane.get` through the server's JSON API socket. This is a client-only patch. It covers only a server on the same computer. For remote endpoints the race stays, unless the client also uses the SSH API bridge (`src/cli/target.rs:66-100`, a large change). The lookup must not block the async client loop, so the patch also reaches `src/client/mod.rs`.
- **B — allow `pane.get` for clients.** Add the read-only `pane.get` to `CLIENT_SHELL_METHODS` (one line, server side). Then use the existing request pattern (`PendingEndpointKind`, as `PaneLinkResolve` in `src/client/shell/actions.rs:499-517`). It breaks the spec constraint "no server changes", and every server that a patched client views must also run the patched build. It is also not enough alone: the server rejects endpoint requests from a client without an active surface (`surface_inactive`, `src/server/headless/endpoint_requests.rs:68-77`; transcript 04 with `pane.rename`). The client cancels requests for an endpoint that is not active (`src/client/shell_runtime.rs:18-34`). But background endpoints still deliver notifications. So a lookup for a background endpoint needs more client and server changes.
- **C — wait for the next snapshot (recommended).** Hold the sound of a pane notification until the client has a snapshot from the same endpoint with a higher revision than at arrival, then read the token there. Give it an expiry, as `AwaitingSnapshot` has (`notification_policy.rs:181-193`). Reason: the server sends the notification after it applied the mute. While the pane keeps its agent, the state change makes the next snapshot differ from the last one sent, so a newer snapshot follows on the same ordered channel and carries the token. The test supports this (29/29). This is not guaranteed when the agent is released before the next render. Then that snapshot has no entry for the pane (see point 5). For a pane that had no agent before, the projection can even be equal to the last one sent, and the server then sends no snapshot (`src/server/headless/render.rs:648-650`, `src/server/client_shell.rs:139-176`). So C also needs a rule for a missing agent entry, absence cannot mean "unmuted", and the expiry can occur on a healthy connection. It is client-only, uses no new API, and works for remote endpoints. The patch is in `notification_policy.rs` plus one field in `ClientPendingNotification` (`src/client/shell/state.rs:738-744`). It changes the spec decision ("query the pane through the existing API"). The behavior on expiry and on a missing agent entry (skip the sound or play it) must also be decided. It relies on 0.9.5 behavior, not on a documented contract.
- **D — accept the race.** Read only the snapshot. A leak can occur in the stale-snapshot cases above. With CLI latency the leak did not occur in 60 of 60 trials, but this is a matter of timing, not a guarantee.

### 7. Lifecycle

The token belongs to the terminal attached to the pane. It is not removed when the pane changes (transcript 02):

- Rename: the token stays.
- Move to a new tab: the token stays.
- Move to a new workspace: the pane ID changes from `w1:p2` to `w2:p1`, the terminal ID stays the same, and the token stays.
- Two client attaches and detaches through a sized pseudo-terminal (rounds 3 and 4; `client connected` and `client detached` in the server log): the token stays. Rounds 1 and 2 did not attach, because the pseudo-terminal had size zero.
- Pane close: the closed pane's terminal is removed (`remove_unattached_terminal_ids`, `src/app/actions.rs:628-646`). `pane get w1:p3` returns `pane_not_found`, and a new split has no token.
- Full server restart: the restored panes keep their ID and label but have no tokens. `session.json` does not contain the token, and every restore path builds `TerminalState::new` with empty tokens (`src/persist/restore.rs:449,594,690`; `src/terminal/state.rs:167-178`).

From the source only (not tested):

- A live `herdr update --handoff` uses the same restore path (`restore_handoff`, `src/persist/restore.rs:96-119`). The mute is lost although the worker processes continue to run.
- A shell respawn keeps the same `TerminalState` and token. It replaces only the runtime and clears the agent identity, not `metadata_tokens` (`src/app/api.rs:633-635`, `src/terminal/state.rs:2327-2347`).

### 8. `pane get` / `pane list`

Both show `"tokens":{"dotfiles_pane_mute":"1"}` (`PaneInfo.tokens`, `src/app/creation.rs:361`; transcript 01). `agent list` and `agent get` show it too (transcript 02). When a pane has no tokens, the response does not include the `tokens` field. It is not shown as `{}`.

### 9. Sound decision and patch size

- The 0.9.5 client always runs in shell mode (`src/client/state.rs:143`). It ignores the legacy `ServerMessage::Notify` sound when a shell exists (`src/client/mod.rs:1792-1800`).
- The only sound decision for completion and needs-input sounds is `ClientShellState::tick_notifications`, at `if let Some(sound) = pending.event.sound` (`src/client/shell/notification_policy.rs:197-210`). There `pending.endpoint_id` and `pending.event.pane_id` are known. The lookup pattern for that endpoint's snapshot agent is in `notification_validation` (same file, lines 333-344).
- A check that reads only the snapshot is about 10 lines in this one file. Because it only removes a `Sound` effect, `handle_shell_notification_effects` still applies `sound_config.allows(agent)` to unmuted panes (`src/client/notifications.rs:52-64`). So unmute cannot force a sound on.
- The patch size for the fix of point 6 depends on the option: C adds roughly 30–50 lines in two files. A and B also need changes in the client loop or the server.

### Decision

The user chose option D for point 6: accept the race. The client reads the mute token only from the snapshot it already has. There is no API lookup, no snapshot wait, and no server change.

Known limitation: a sound can leak when the state change of a muted pane comes within one render interval of the mute (normally 16 ms), because the notification can then reach the client before the snapshot with the token. The split → mute → run workflow keeps this window small: the worker starts only after the mute command returns, and an agent start takes much longer than one render interval. Tests cover the order snapshot → notification, not this race.
