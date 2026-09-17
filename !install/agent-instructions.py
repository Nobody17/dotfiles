#!/usr/bin/env python3
"""Install automatic machine-local context for Codex and Pi; preserve other hooks."""

import json
from pathlib import Path


def install(home: Path) -> None:
    local = home / ".agents/local.md"
    previous = home / ".config/agent-instructions/local.md"
    if previous.exists() and local.exists() and previous.read_bytes() != local.read_bytes():
        raise RuntimeError("Both local instruction files exist with different contents")
    append = home / ".pi/agent/APPEND_SYSTEM.md"
    if append.is_symlink():
        if append.resolve() not in (local.resolve(), previous.resolve()):
            raise RuntimeError(f"Existing Pi prompt link points elsewhere: {append}")
    elif append.exists():
        raise RuntimeError(f"Preserve the existing Pi prompt before installing: {append}")

    hooks_path = home / ".codex/hooks.json"
    configuration = json.loads(hooks_path.read_text()) if hooks_path.exists() else {}
    groups = configuration.setdefault("hooks", {}).setdefault("SessionStart", [])
    group = {
        "hooks": [{
            "type": "command",
            "command": 'if [ -f "$HOME/.agents/local.md" ]; then cat "$HOME/.agents/local.md"; fi',
            "timeout": 5,
            "statusMessage": "Loading machine-local instructions",
            "additionalContextLimit": 16000,
        }],
    }
    old_command = 'if [ -f "$HOME/.config/agent-instructions/local.md" ]; then cat "$HOME/.config/agent-instructions/local.md"; fi'
    migrated = False
    for existing in groups:
        for handler in existing.get("hooks", []):
            if handler.get("command") == old_command:
                handler["command"] = group["hooks"][0]["command"]
                migrated = True
    changed = group not in groups
    if changed:
        groups.append(group)

    local.parent.mkdir(parents=True, exist_ok=True)
    if previous.exists():
        if not local.exists():
            previous.rename(local)
        else:
            previous.unlink()
    if not local.exists():
        local.touch(exist_ok=False)
    append.parent.mkdir(parents=True, exist_ok=True)
    if append.is_symlink() and append.resolve() != local.resolve():
        append.unlink()
    if not append.is_symlink():
        append.symlink_to(local)
    if changed or migrated:
        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        if hooks_path.exists():
            backup = hooks_path.with_name("hooks.json.before-local-instructions")
            if not backup.exists():
                backup.write_bytes(hooks_path.read_bytes())
        hooks_path.write_text(json.dumps(configuration, indent=2) + "\n")


if __name__ == "__main__":
    install(Path.home())
    print("Installed Pi prompt link and Codex SessionStart hook.")
    print("In Codex, review and trust 'Loading machine-local instructions' with /hooks.")
