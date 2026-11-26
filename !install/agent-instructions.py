"""Install automatic machine-local context for Codex, Pi and Antigravity, and agy defaults; preserve other hooks."""

import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def antigravity_links(home: Path) -> dict[Path, Path]:
    """Antigravity (app and agy CLI) reads ~/.gemini/config; point it at the shared agent files."""
    configuration = home / ".gemini/config"
    return {
        configuration / "skills": home / ".agents/skills",
        # rules/*.md would need YAML frontmatter, which Claude and Pi would then read too.
        # GEMINI.md loads always, without frontmatter, next to AGENTS.md.
        configuration / "GEMINI.md": home / ".agents/local.md",
    }


def with_auto_agent_mode(settings: dict) -> dict:
    """agy settings that start sessions in Auto mode, unless this machine already chose a mode."""
    # agy 1.5.7 made Auto the default, but only where no mode is saved; earlier versions start in Default.
    return settings if "agentMode" in settings else {**settings, "agentMode": "auto"}


def skill_read_allow_rules(home: Path, repository_root: Path = REPOSITORY_ROOT) -> list[str]:
    """agy read_file rules covering the config link, shared skills, and stowed repo skills."""
    skill_directories = (
        home / ".gemini/config/skills",
        home / ".agents/skills",
        repository_root / "agents/.agents/skills",
    )
    return [f"read_file({directory})" for directory in skill_directories]


def with_skill_read_permissions(
    settings: dict,
    home: Path,
    repository_root: Path = REPOSITORY_ROOT,
) -> dict:
    """agy settings that allow reading global skills without prompting, preserving other rules."""
    permissions = settings.get("permissions", {})
    if not isinstance(permissions, dict):
        raise ValueError("agy settings 'permissions' must be a JSON object")
    existing_allow_rules = permissions.get("allow", [])
    if not isinstance(existing_allow_rules, list):
        raise ValueError("agy settings 'permissions.allow' must be a JSON array")
    merged_allow_rules = list(existing_allow_rules)
    for rule in skill_read_allow_rules(home, repository_root):
        if rule not in merged_allow_rules:
            merged_allow_rules.append(rule)
    return {
        **settings,
        "permissions": {
            **permissions,
            "allow": merged_allow_rules,
        },
    }


def blocked_links(links: dict[Path, Path]) -> list[Path]:
    """Paths that hold something other than the wanted link."""
    return [
        link for link, target in links.items()
        if (link.is_symlink() and link.resolve() != target.resolve())
        or (link.exists() and not link.is_symlink())
    ]


def make_links(links: dict[Path, Path]) -> None:
    for link, target in links.items():
        if not link.is_symlink():
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(target)


def install(home: Path, repository_root: Path = REPOSITORY_ROOT) -> None:
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
    links = antigravity_links(home)
    blocked = blocked_links(links)
    if blocked:
        raise RuntimeError(f"Move these Antigravity files away before installing: {blocked}")
    # agy writes trustedWorkspaces into this file, so the repo cannot own it; merge defaults instead.
    agy_settings_path = home / ".gemini/antigravity-cli/settings.json"
    agy_settings = json.loads(agy_settings_path.read_text()) if agy_settings_path.exists() else {}
    if not isinstance(agy_settings, dict):
        raise ValueError("agy settings must be a JSON object")
    wanted_agy_settings = with_skill_read_permissions(
        with_auto_agent_mode(agy_settings),
        home,
        repository_root,
    )

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
    make_links(links)
    if wanted_agy_settings != agy_settings:
        agy_settings_path.parent.mkdir(parents=True, exist_ok=True)
        agy_settings_path.touch(mode=0o600)
        agy_settings_path.write_text(json.dumps(wanted_agy_settings, indent=2) + "\n")
    if changed or migrated:
        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        if hooks_path.exists():
            backup = hooks_path.with_name("hooks.json.before-local-instructions")
            if not backup.exists():
                backup.write_bytes(hooks_path.read_bytes())
        hooks_path.write_text(json.dumps(configuration, indent=2) + "\n")


if __name__ == "__main__":
    install(Path.home())
    print(
        "Installed Pi prompt link, Antigravity links, agy defaults (Auto mode + skill read permissions) "
        "and Codex SessionStart hook."
    )
    print("In Codex, review and trust 'Loading machine-local instructions' with /hooks.")
