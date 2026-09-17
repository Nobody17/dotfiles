Shared agent files
==================

`~/.agents/` stays a real directory. Stow links tracked files from this package
with `--no-folding`. Add your own shared skills under `.agents/skills/` here;
add a corresponding link under `claude/.claude/skills/` and allow it in the
root `.gitignore` for Claude discovery. Codex and Pi discover this directory
directly.

Third-party skills installed into `~/.agents/skills/` stay outside the repo.
Use `./stow.fish --no-adopt agents claude codex pi` to avoid adopting installed
files, then `python3 '!install/agent-instructions.py'` for automatic local
context loading. `~/.agents/local.md` is machine-local and never stowed.

See [the loading setup](../codex/README.md) for each agent and Codex hook trust.
