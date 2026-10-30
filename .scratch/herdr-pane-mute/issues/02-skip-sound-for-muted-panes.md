# 02: Skip Herdr sounds for muted panes

Status: ready-for-agent
Blocked by: 01

**What to build:** A local client patch that skips automatic completion and needs-input sounds for panes that carry the mute token from ticket 01. Store it in `mise/.config/mise/herdr-local/` so it builds in an isolated source checkout. Automatic installation is ticket 04.

**Mute token (ticket 01):**

```sh
# mute
herdr pane report-metadata <pane_id> --source dotfiles:pane-mute --token dotfiles_pane_mute=1
# unmute
herdr pane report-metadata <pane_id> --source dotfiles:pane-mute --clear-token dotfiles_pane_mute
```

A pane is muted when its token `dotfiles_pane_mute` is present with any value.

**Patch location (Herdr 0.9.5):** `ClientShellState::tick_notifications` in `src/client/shell/notification_policy.rs`, at `if let Some(sound) = pending.event.sound` (line 197). There `pending.endpoint_id` and `pending.event.pane_id` are known. Do not push the `Sound` effect when the client's current snapshot for that endpoint has an agent entry for that pane whose `tokens` contain `dotfiles_pane_mute`. The lookup pattern for that agent entry is in `notification_validation` in the same file (lines 333-344). Clients receive tokens only in `ClientShellAgent.tokens`, not in `ClientShellPane`.

**Approach (user decision, ticket 01 option D):** read the token only from the snapshot the client already has. Do not query the API, do not wait for a newer snapshot, and do not change the server. A pane without an agent entry in the snapshot counts as unmuted.

**Known limitation (accepted, not tested):** a notification can reach the client before the snapshot with the token when the state change comes within one render interval of the mute (normally 16 ms). Then a sound can leak. See ticket 01, point 6 and Decision.

**Build environment from ticket 01:** under `/Users/eric/.local/state/orchestrate-tickets/herdr-pane-mute-20261030/evidence/t01/`:

- the unpacked Herdr 0.9.5 source: `src/herdr-0.9.5`
- Rust 1.96.1 in `toolchain/rustup`; use it with `RUSTUP_HOME=<that dir>`, `CARGO_HOME=<evidence>/toolchain/cargo`, and `/opt/homebrew/bin/rustup run 1.96.1 cargo …`
- Zig 0.16.0: `toolchain/zig-aarch64-macos-0.16.0/zig`, added to `PATH`

Copy the source before you patch it, or build in your own scratch directory. Keep build outputs outside the repository. In ticket 01, Claude Code auto mode blocked a build of the downloaded source, because the build runs downloaded build scripts. The worker for this ticket may need the user's permission to build.

- [ ] A pane with the mute token plays neither completion nor needs-input sound. A pane without it, including one with the same agent type, keeps its existing behavior.
- [ ] Unmute (clearing the token) restores the existing policy and does not override a global or agent-type sound disable.
- [ ] Toasts, notification navigation, agent status, wait behavior, and terminal bells do not change. A muted pane is not marked seen or complete.
- [ ] Ordering test: the test starts unmuted. It delivers the snapshot with the token through the same path Herdr uses for a received snapshot (`src/client/shell_runtime.rs:641-660`): `ClientShellState::set_endpoint_snapshot_for_generation` for the active endpoint with an active surface and no pending projection, otherwise `cache_endpoint_snapshot_inactive_for_generation`. Cover both paths, because background endpoints also deliver notifications. Then the test delivers the notification for that pane (`receive_notification`), and expects no sound. The accepted race (notification before the snapshot) is a known limitation, not a tested guarantee.
- [ ] The patch touches only the sound decision. No new CLI commands, no rendering changes, no server or wire changes.
- [ ] The behavioral tests can run on their own (one documented command), because ticket 04 runs them during each install.
- [ ] Tests at the existing client notification-policy boundary cover the cases above with deterministic notification inputs. No real models, no audible speakers.
- [ ] Relevant upstream checks and compatibility fixtures pass without changed protocol expectations.
