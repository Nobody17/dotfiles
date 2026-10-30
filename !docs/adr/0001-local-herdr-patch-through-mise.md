# Maintain a local Herdr patch through mise

Pane-specific muting is needed locally while Herdr continues to receive upstream updates through mise. Keep the change as a local source patch and rebuild the matching upstream release during installation, instead of publishing a fork or maintaining an independently updated executable. This preserves the existing update workflow at the cost of local compilation and occasional patch repairs when upstream code changes.

The feature must be installable from this dotfiles repository on macOS and Linux. Store the build hook and patch under the portable `mise/.config/mise/herdr-local/` package, using the stowed configuration location rather than an absolute checkout path. Keep build caches and mute state outside the repository and independent on each computer. Keep the existing macOS-only Herdr configuration separate because it contains AeroSpace bindings. Native Windows is outside this version's scope.

The existing bootstrap installs system prerequisites, links dotfiles, then runs mise. Preserve that order, retain rustup ownership of Rust, and provide the Zig version required by the upstream release as an ordered build dependency. A fresh installation must not depend on an authenticated GitHub CLI. Linux installation needs verification separately from the local macOS build.

The intended integration is a tool-specific mise postinstall script. Mise 2026.10.23 keeps a new version incomplete until that script succeeds, excluding failed installations from `latest` selection. Initial adoption must stage the patched executable before replacement; forcing a reinstall of the existing version could remove the working copy first.

Pane mute silences Herdr completion and needs-input sounds while retaining terminal bells, toasts, badges, and real agent state. All local Herdr clients share the preference, including after detach and reconnect, until the originating server restarts. Other computers keep independent preferences. This requires local persisted state rather than an in-memory client-only set.

Inspection of Herdr v0.9.5 found that terminal-bell messages discard their pane identity before reaching the client. The user accepted leaving terminal bells unchanged to avoid the server protocol changes needed for full sound suppression. This replaces the initial all-sounds proposal.

The primary use case is a parent agent creating muted worker panes. Agent-accessible creation and mute controls are required; a keyboard-only interface is insufficient. The user has no preference about retaining mute when a worker is replaced: choose the simpler implementation without special worker-replacement handling. The accepted interface is explicit `pane split --muted` plus mute/unmute commands for existing panes, with agent instructions describing the worker workflow. It saves the mute before returning the new pane to the parent, so subsequent worker startup is muted; this does not promise to suppress shell startup events before the creation command returns.

The user approved two test boundaries: the existing Herdr command/client-notification flow, and the dotfiles installer entry point. Test observable sound effects, preserved notifications and status, and update recovery rather than private helper calls.

This repository uses `!docs/` because `stow.fish` treats ordinary top-level directories as packages to link into the home directory.

Parts of this decision are superseded by ADR 0002 (pane mute as server pane metadata).
