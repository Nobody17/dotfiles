Shared global instructions live in `agents/.agents/AGENTS.md` (installed as `~/.agents/AGENTS.md`), tracked by this
repository. Codex links to it and Claude imports it.

Machine-local instructions live in `~/.agents/local.md`,
outside the repository. Each application adds their contents automatically:

- Claude imports the file from its global `CLAUDE.md`.
- Pi reads its global `APPEND_SYSTEM.md`, a local symlink to the file.
- Codex runs a global `SessionStart` hook which outputs the file as developer
  context on startup, resume, clear, and compaction. No matcher restricts it.

Install the shared links with `./stow.fish --no-adopt agents codex claude pi`, then run
`python3 '!install/agent-instructions.py'`. The installer preserves existing
Codex hooks and local instructions. It stops if Pi already has a different
appended system prompt, so those instructions can be merged deliberately.

In Codex, open `/hooks` and trust `Loading machine-local instructions` once.
Codex skips untrusted hooks. Restart sessions after setup or instruction edits.
The Codex hook allows approximately 16,000 tokens before output is shortened;
keep machine-local instructions below that limit.

This setup uses the default application home directories and POSIX shell.

References: [Codex hooks](https://learn.chatgpt.com/docs/hooks),
[Claude imports](https://code.claude.com/docs/en/memory),
[Pi system prompt](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent#system-prompt).
