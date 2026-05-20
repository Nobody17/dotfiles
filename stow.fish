#!/usr/bin/env fish

cd (dirname (status filename))

if git status --porcelain | string length -q
    echo "❌ Aborting: You have uncommitted or unstaged changes in this repository."
    echo "Please commit, stash, or discard them before running this script to prevent data loss."
    exit 1
end

stow --verbose --target=$HOME --adopt --restow */

if git status --porcelain | string length -q
    echo ""
    echo "⚠️  The following repository files were overwritten by your local system configurations:"
    echo "--------------------------------------------------------------------------------"
    git status --short
    echo "--------------------------------------------------------------------------------"
    
    read -l -P "Do you want to overwrite these local files with your clean repo versions? [y/N]: " confirm

    if string match -ri '^[yY](es)?$' -- "$confirm"
        git restore .
        echo "🔄 Repository versions restored successfully."
    else
        echo "❌ Restoration aborted. Keeping your local changes inside the repository folder."
    end
else
    echo "✅ No conflicting local files found. Everything is cleanly linked!"
end

if test -f $HOME/.config/fish/config.fish
    source $HOME/.config/fish/config.fish
end

if set -q HYPRLAND_INSTANCE_SIGNATURE; and test -d $HOME/.config/hypr
    echo "Hyprland detected. Reloading configuration..."
    hyprctl reload
end
