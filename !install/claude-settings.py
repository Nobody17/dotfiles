"""Write ~/.claude/settings.json from the tracked base settings and the private settings of this machine.

The repository is public, so it cannot hold everything. claude/.claude/settings.base.json
holds the settings for every machine. ~/.claude/settings.private.json holds the settings that
must stay off GitHub, such as the autoMode block about the trusted infrastructure at work.
Claude Code reads autoMode only from the user settings, never from project settings, so the
private part must end up in ~/.claude/settings.json too.

~/.claude/settings.json is a real file, not a symlink. Claude Code writes into it (/model,
/config, /auto-mode-setup), and a symlink would put those writes into the repository.

Run this script again after a change to either file. The base wins over the current file,
and the private file wins over both. A key that only Claude Code wrote stays. Objects merge
key by key; any other value, a list too, replaces the earlier value.
"""

import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def merged_settings(earlier: dict, later: dict) -> dict:
    """earlier with each key of later on top; nested objects merge key by key."""
    result = dict(earlier)
    for key, later_value in later.items():
        earlier_value = result.get(key)
        if isinstance(earlier_value, dict) and isinstance(later_value, dict):
            result[key] = merged_settings(earlier_value, later_value)
        else:
            result[key] = later_value
    return result


def read_settings_object(path: Path) -> dict:
    """The JSON object in path, or an empty object if the file does not exist."""
    if not path.exists():
        return {}
    settings = json.loads(path.read_text())
    if not isinstance(settings, dict):
        raise ValueError(f"{path} must hold a JSON object")
    return settings


def is_inside(path: Path, folder: Path) -> bool:
    return path.resolve().is_relative_to(folder.resolve())


def install(home: Path, repository_root: Path = REPOSITORY_ROOT) -> bool:
    """Write the merged settings. Return True if the file changed."""
    base_path = repository_root / "claude/.claude/settings.base.json"
    private_path = home / ".claude/settings.private.json"
    live_path = home / ".claude/settings.json"

    # Earlier setups linked the live file into this repository with stow.
    live_is_old_link = live_path.is_symlink()
    if live_is_old_link and not is_inside(live_path, repository_root):
        raise RuntimeError(f"{live_path} is a symlink to a place outside the repository; move it away first")

    current = read_settings_object(live_path)
    wanted = merged_settings(merged_settings(current, read_settings_object(base_path)), read_settings_object(private_path))
    if wanted == current and not live_is_old_link:
        return False

    if live_is_old_link:
        live_path.unlink()
    live_path.parent.mkdir(parents=True, exist_ok=True)
    live_path.touch(mode=0o600)
    live_path.write_text(json.dumps(wanted, indent=2, ensure_ascii=False) + "\n")
    return True


if __name__ == "__main__":
    changed = install(Path.home())
    print("Wrote ~/.claude/settings.json." if changed else "~/.claude/settings.json is up to date.")
