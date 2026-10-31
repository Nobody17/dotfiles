# 04: Install and upgrade patched Herdr through mise

Status: ready-for-agent
Blocked by: 02

**What to build:** A tool-specific mise postinstall hook that builds the exact Herdr release that mise selected, with the local patch, on macOS and Linux. Normal `mise install` and `mise up` produce a patched release. A failed patch or build leaves the new version incomplete, so the previous working release stays selected.

- [x] The hook and patch live in `mise/.config/mise/herdr-local/` and are referenced through the stowed config location. They work from any checkout path, including one with spaces.
- [x] The hook uses the version and install directory that mise supplies, fetches the matching upstream source tag without the GitHub CLI or credentials, and applies the patch.
- [x] The bootstrap order stays: system prerequisites, dotfiles linking, mise. Rust stays with rustup. Zig is an ordered mise build dependency. Missing prerequisites give an actionable error.
- [x] The build runs in a temporary directory. The hook runs the patch's behavioral tests from ticket 02 on the patched source, builds the release, and checks that the binary starts (`herdr --version`). It replaces the executable only after all three succeed.
- [x] On success, a stamp file next to the executable records the upstream version and patch hash.
- [x] Any failure exits non-zero with the failed step and version. It never installs an unpatched binary, and it never stops servers or terminates panes.
- [x] Unittest runs the hook as a process with temporary directories and stubbed download and compilation. It covers success, patch conflict, and build failure, and asserts that the previous executable stays intact after a failure.
- [x] Manual check, recorded in the ticket: with real mise in an isolated data directory, a failing postinstall leaves the version incomplete and `latest` still selects the previous version.
- [ ] Manual smoke checks on macOS and Linux **macOS passed; Linux is an open gap (not run). See Manual checks.**, including a fresh setup without GitHub credentials. Report an unavailable platform as an open gap.
- [x] Documentation covers: prerequisites, normal updates, how to check the stamp of the active build, what to do on a patch conflict, the manual initial adoption on a computer that already has Herdr, and that running servers keep the old binary until the user restarts them.

## Manual checks

Raw logs: `~/.local/state/orchestrate-tickets/herdr-pane-mute-20261030/evidence/t04/`. Every counted run used real mise 2026.10.23 through the isolated wrapper `~/.local/state/orchestrate-tickets/herdr-pane-mute-20261030/bin/mise-iso`: own `HOME`, XDG, `MISE_*`, `RUSTUP_HOME` and `CARGO_HOME`, a minimal `PATH` without `gh`, and no GitHub token variables (the wrapper script sets these; `smoke-macos.log` shows no `gh` on `PATH`). Each logged `mise install` started from `/`. The mise package of a checkout copy was stowed into the scenario `HOME`.

**Failing postinstall** (`postinstall-failure.log`). First `herdr = "0.9.4"` without the hook: 0.9.4 installed. Then the repository configuration (`herdr = "latest"` with the hook) and a patch changed so that it conflicts (one changed context line, reported by the worker, not in the log): `mise install zig herdr` installed Zig 0.16.0 first, ran the hook through `${MISE_CONFIG_FILE%/*}/herdr-local/postinstall.sh` (stowed path into a checkout folder with a space, reported by the worker, not in the log), and the hook stopped with `step "apply pane-mute.patch" failed for Herdr 0.9.5`. mise reported `✗ herdr@0.9.5` and wrote `incomplete-installs/herdr/0.9.5/incomplete`. After that, `mise current herdr`, `mise latest --installed herdr` and `mise where herdr` gave 0.9.4, the `latest` link pointed to 0.9.4, and `mise exec herdr -- herdr --version` printed `herdr 0.9.4`. A second `mise install` ran the hook again for 0.9.5.

**macOS smoke** (`smoke-macos.log`, macOS arm64). Checkout copy at `.../evidence/t04/checkout with spaces/dotfiles`. The scenario started fresh in run 2 (see below), and the successful run 3 continued it: `mise install zig herdr` found Zig 0.16.0 already installed, then ran herdr 0.9.5 through all hook steps: the patch tests reported `5 passed`, the release built, `herdr --version` printed `herdr 0.9.5`, and the hook installed the binary in 336 s. Afterwards `mise current herdr` gave 0.9.5, `mise exec herdr -- herdr --version` printed `herdr 0.9.5`, and the stamp gave `upstream_version=0.9.5` and the SHA-256 of `~/.config/mise/herdr-local/pane-mute.patch`. The installed binary differs from the upstream release binary. No `herdr-local.*` build folder was left in `TMPDIR`.

Run 2, the first one in a fresh scenario, found a defect: with Homebrew's rustup there are no proxies in `~/.cargo/bin`, so `rustup run <toolchain> cargo` could not find `rustc` (`smoke-macos.rustc-path-defect-run2.log`). The hook now puts the toolchain's own `bin` folder first on `PATH`, and the cargo stub of the unittest needs `rustc` on `PATH`. In run 2, mise installed Zig 0.16.0 into the fresh scenario, and the hook installed Rust 1.96.1 through rustup and got as far as the patch tests. Run 3 reused that scenario: its mise data with Zig and the incomplete herdr 0.9.5, and the Rust toolchain.

Smoke run 1 ran into the anonymous GitHub API limit of 60 requests an hour before the hook started (`smoke-macos.rate-limited-run1.log`); its mise data was deleted before run 2 (reported by the worker, not in the log). The first failure-check run is discarded (`postinstall-failure.discarded-run1.log`): mise also read the real `~/.config/mise/config.toml` as a project file, because the run started under `/Users/eric` (reported by the worker, not in the log). It wrote only into the isolated data folder, which was then deleted (reported by the worker, not in the log). mise asks the API for the herdr release before the hook runs; the hook itself does not use the API. The README says what to do.

**Linux smoke: open gap.** Not run: no Linux computer, and Docker was not allowed (disk).
