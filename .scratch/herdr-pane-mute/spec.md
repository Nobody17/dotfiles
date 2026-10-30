# Herdr pane mute with a mise-managed local patch

## Problem Statement

A parent agent creates worker panes to delegate work. Every worker completion or request for input can produce a Herdr notification sound, even when the parent is already supervising that worker. Global sound controls silence the parent as well, and controls by agent type cannot distinguish a parent and worker using the same agent.

The user needs agents to mute worker panes through commands. The customization must live in the dotfiles repository, install on macOS and Linux, and survive Herdr updates through mise without a published fork or manual patching after routine updates.

## Solution

Store pane mute as pane metadata on the Herdr server, using the existing `herdr pane report-metadata` command with a uniquely prefixed token name, for example `dotfiles_pane_mute`. A small local patch makes the client skip completion and needs-input sounds for panes that carry this token. The server needs no patch and the wire protocol does not change.

A parent creates a worker pane with the normal `pane split`, mutes it, waits for the mute command to succeed, then starts and prompts the worker.

Because the mute lives on the server pane:

- every client attached to that server sees it, including after detach and reopen;
- it follows the pane through moves and renames;
- it disappears when the pane closes or the server restarts.

A mute set on a server applies to every patched client that views that server, on any computer. Unpatched clients keep playing sounds.

A tool-specific mise postinstall hook builds the exact upstream release with the local patch. A failed build leaves the mise version incomplete, so the previous working release stays selected.

## User Stories

1. As a parent agent, I want to mute a pane by its ID, so that routine worker activity does not interrupt the user.
2. As a parent agent, I want the mute to be in effect on the server when the mute command returns, so that a worker started afterward does not outrun it. A state change within one render interval of the mute can still play a sound (accepted limitation, ticket 01).
3. As a parent agent, I want to unmute a pane, so that it can notify the user when its role changes.
4. As a parent agent, I want mute to leave agent state and wait behavior intact, so that orchestration still detects completion and blocked workers.
5. As a parent agent, I want installed instructions for the split → mute → run workflow, so that I do not need to rediscover the commands.
6. As a user, I want muted panes to emit neither Herdr completion sounds nor needs-input sounds.
7. As a user, I want my parent agent and unrelated panes, including panes running the same agent type, to remain audible.
8. As a user, I want toasts, status badges, and terminal bells to keep their current behavior.
9. As a user, I want unmuting to restore the existing sound policy, so that mute never forces sound on.
10. As a user, I want mute to survive detach and reopen, follow moved or renamed panes, and reset after a server restart.
11. As a dotfiles user, I want to install the feature on macOS and Linux through the existing setup flow, from any checkout location, without GitHub credentials.
12. As a user, I want normal mise upgrades to reapply the patch, and a failed patch or build to keep my previous working Herdr.

## Constraints for all tickets

- Keep the patch as small as possible. Every patched file is a possible conflict on upstream upgrades.
- Do not change server behavior, server methods, or frozen wire codecs.
- Do not stop or restart a live Herdr server, and do not use the user's live panes as test fixtures.
- Keep patch assets and the build hook in the portable `mise/.config/mise/herdr-local/` package. Keep build outputs and caches outside the repository. Do not embed the checkout path or username.
- Keep the macOS-only Herdr configuration and its AeroSpace bindings separate.
- Report any platform or check you could not run as an open gap, not as a pass.

## Implementation Decisions

- Mute is a metadata token on the server pane, written through the existing `report-metadata` command. Herdr keeps tokens in one flat map by token name for each pane; `--source` does not separate token names. So the token name carries a unique prefix, for example `dotfiles_pane_mute`. Ticket 01 confirms the exact command, that the name is valid, that the token stays until it is cleared, and that no other integration writes the same name.
- Do not add new CLI commands. Agents mute and unmute with the documented `report-metadata` command.
- Do not add a `--muted` option to `pane split`. The ordered split → mute → run workflow gives the same server-side guarantee (the mute is on the server before the worker starts) without patching split.
- The client patch filters automatic completion and needs-input sounds at the client notification boundary, before playback. It reads the token from pane state that the client already has. Clients receive tokens through snapshots, and the existing sound decision does not wait for a fresh snapshot. Ticket 01 showed that a notification can reach the sound decision before the snapshot with a new token. The user accepted this race: the client reads the token only from the snapshot it already has, with no API lookup and no snapshot wait. A sound can leak when the state change comes within one render interval of the mute.
- Pane mute only adds suppression. Toasts, notification navigation, agent state, badges, and terminal bells do not change.
- No visible mute indicator in this version. `herdr pane get` and `herdr pane list` show the mute state if they already show metadata tokens.
- The mise postinstall hook builds in a temporary directory. It runs the patch's behavioral tests on the patched source, builds the release, checks that the binary starts (`herdr --version`), and replaces the executable only after all of this succeeds. The binary itself does not need a feature proof. It records the upstream version and patch hash in a stamp file next to the executable. It does not keep its own build cache, locking, or repair command.
- Preserve the bootstrap order: system prerequisites, dotfiles linking, then mise. Rust stays with rustup. Zig is an ordered mise build dependency. Fetch source without the GitHub CLI.
- Initial adoption on a computer that already has Herdr installed is a documented manual step, not installer logic.

## Testing Decisions

- Herdr side: a few behavioral tests at the existing client notification-policy boundary, stored in the patch. One ordering test starts unmuted, delivers the snapshot with the token through the same path Herdr uses, then delivers the notification, and expects no sound; an already-muted fixture does not replace it. The accepted race is a known limitation, not a tested guarantee. Ticket 02 gives the exact path. Muted pane gets no completion or needs-input sound. Unmuted pane with the same agent type still gets sound. Toasts and status do not change. Unmute does not override a global or agent-type sound disable.
- Installer side: standard-library unittest that runs the hook as a process with temporary directories and stubbed download and compilation. Cover success, patch conflict, and build failure. Assert that the previous executable stays intact after a failure.
- Manual checks: one real mise check that a failed postinstall leaves the version incomplete and not selected. Build/install smoke checks on macOS and Linux, including a fresh setup without GitHub credentials and a checkout path with spaces.

## Out of Scope

- Terminal bells, audio produced directly by applications, and operating-system sounds.
- Muting toasts, hiding badges, or treating a muted worker as seen or complete.
- A visible mute indicator in the client.
- Per-computer mute preferences. Mute belongs to the server pane.
- `pane split --muted`, mute inheritance, name rules, timed snoozes, and separate completion/needs-input controls.
- Installer concurrency handling, build cache reuse, and a repair command.
- Native Windows, publishing a fork, or upstream contribution.
- A guarantee that every future upstream release accepts the patch without maintenance.

## Further Notes

Herdr 0.9.5 terminal-bell messages discard the originating pane identity, so per-pane bell suppression would need server and protocol changes. The user accepted the narrower Herdr-sounds-only scope.

Investigation used Herdr 0.9.5 and mise 2026.10.23. That mise release keeps an installation incomplete until tool-specific postinstall succeeds. The Herdr release requires Rust 1.96.1 and Zig 0.16.0. Select prerequisites from the release being built.

See ADR 0001 for the local-patch approach and ADR 0002 for the decision to store mute as server pane metadata.
