# Local Herdr patch

`pane-mute.patch` is the local patch for Herdr 0.9.5. It changes only the client sound decision. A patched client plays no completion sound and no needs-input sound for a pane that has the metadata token `dotfiles_pane_mute`. Toasts, notification navigation, agent status, wait behavior, and terminal bells do not change. The patch does not change the server, the wire protocol, or the CLI.

Mute and unmute a pane with the existing Herdr command:

```sh
herdr pane report-metadata <pane_id> --source dotfiles:pane-mute --token dotfiles_pane_mute=1
herdr pane report-metadata <pane_id> --source dotfiles:pane-mute --clear-token dotfiles_pane_mute
```

The client reads the token from the last snapshot that it received from the server. A pane without an agent entry in that snapshot counts as unmuted. When a state change comes within one render interval of the mute (normally 16 ms), the notification can arrive before the snapshot with the token, and the sound can still play. This is a known limitation.

## Behavioral tests

Apply the patch to the source of the matching upstream release, then run the tests from the root of that source tree:

```sh
cargo test --locked --bin herdr notification_policy::pane_mute_tests::
```

The build needs the Rust and Zig versions that the release requires (Herdr 0.9.5: Rust 1.96.1, Zig 0.16.0 on `PATH`). The command exits non-zero when a test fails. But it exits 0 when the filter matches no test, so also check that the summary line reports `5 passed`.
