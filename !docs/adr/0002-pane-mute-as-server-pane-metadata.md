# Store pane mute as server pane metadata

Supersedes the state and scope parts of ADR 0001: "local persisted state", "other computers keep independent preferences", `pane split --muted`, and the required visible indicator.

A client-local mute store needs identity keys for endpoint, session, and terminal, atomic locked writes, session freshness checks, and its own restart-reset logic. Herdr 0.9.5 already keeps display-only pane metadata on the server through `herdr pane report-metadata`. A token with a unique name such as `dotfiles_pane_mute` gets client sharing, detach survival, move and rename, pane-close cleanup, and restart reset from the server, without a server patch or wire change. The local patch shrinks to the client sound decision. Herdr keeps tokens in one flat map by token name, and `--source` does not separate names, so the unique prefix is what protects the flag from other integrations.

The cost: a mute applies to every patched client that views that server, on any computer, not to one computer only. The user accepted this. A spike (ticket 01) confirms that the token behaves as required before implementation. If it does not, the user decides the fallback; a client-local store is not the automatic fallback.

Further simplifications accepted with this decision: no `pane split --muted` (the split → mute → run workflow gives the same ordering guarantee), no new CLI commands (agents use `report-metadata` directly), no visible client indicator in this version, and an installer without its own locking, build cache, or repair command. Initial adoption on a computer with Herdr already installed is a documented manual step.
