#!/usr/bin/env fish

# mise owns every language runtime and CLI tool. The list lives in
# mise/.config/mise/config.toml in this repo, stowed to ~/.config/mise.

if not command -v mise > /dev/null
    if command -v paru > /dev/null
        paru -S --needed mise || exit 1
    else
        curl -fsSL https://mise.run | sh || exit 1
        fish_add_path -g "$HOME/.local/bin"
    end
end

if not command -v mise > /dev/null
    echo "Error: mise was not found after installation."
    exit 1
end

# Needs the stowed config, so stow.fish must have run first.
mise install || exit 1

mise doctor > /dev/null 2>&1
echo "Success: mise manages "(mise ls --current 2>/dev/null | wc -l)" tools."
