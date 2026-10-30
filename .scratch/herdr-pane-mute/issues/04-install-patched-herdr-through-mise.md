# 04: Install and upgrade patched Herdr through mise

Status: ready-for-agent
Blocked by: 02

**What to build:** A tool-specific mise postinstall hook that builds the exact Herdr release that mise selected, with the local patch, on macOS and Linux. Normal `mise install` and `mise up` produce a patched release. A failed patch or build leaves the new version incomplete, so the previous working release stays selected.

- [ ] The hook and patch live in `mise/.config/mise/herdr-local/` and are referenced through the stowed config location. They work from any checkout path, including one with spaces.
- [ ] The hook uses the version and install directory that mise supplies, fetches the matching upstream source tag without the GitHub CLI or credentials, and applies the patch.
- [ ] The bootstrap order stays: system prerequisites, dotfiles linking, mise. Rust stays with rustup. Zig is an ordered mise build dependency. Missing prerequisites give an actionable error.
- [ ] The build runs in a temporary directory. The hook runs the patch's behavioral tests from ticket 02 on the patched source, builds the release, and checks that the binary starts (`herdr --version`). It replaces the executable only after all three succeed.
- [ ] On success, a stamp file next to the executable records the upstream version and patch hash.
- [ ] Any failure exits non-zero with the failed step and version. It never installs an unpatched binary, and it never stops servers or terminates panes.
- [ ] Unittest runs the hook as a process with temporary directories and stubbed download and compilation. It covers success, patch conflict, and build failure, and asserts that the previous executable stays intact after a failure.
- [ ] Manual check, recorded in the ticket: with real mise in an isolated data directory, a failing postinstall leaves the version incomplete and `latest` still selects the previous version.
- [ ] Manual smoke checks on macOS and Linux, including a fresh setup without GitHub credentials. Report an unavailable platform as an open gap.
- [ ] Documentation covers: prerequisites, normal updates, how to check the stamp of the active build, what to do on a patch conflict, the manual initial adoption on a computer that already has Herdr, and that running servers keep the old binary until the user restarts them.
