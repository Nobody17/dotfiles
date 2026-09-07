#!/usr/bin/env fish

# Order matters:
#   1. system layer   brew (macOS), paru (Arch) or apt (Debian) —
#                     compilers, libs, stow, mise
#   2. stow           links this repo into $HOME, including the mise config
#   3. mise           reads that config and installs every runtime and CLI tool
#
# Step 3 depends on step 2, so do not reorder these.
#
# A fresh Mac has no fish, so this script cannot start there. Bootstrap first:
#   bash '!install/brew.sh'
# That installs fish. Then run this script with the new fish.

cd (dirname (status filename))

mkdir -p ~/.local/bin
fish_add_path -g ~/.local/bin

function run_step
    set -l script $argv[1]
    if not test -f $script
        return 0
    end
    echo "==> $script"
    fish $script
    if test $status -ne 0
        echo "Error: $script failed."
        exit 1
    end
end

# 1. System layer
if test (uname) = Darwin
    # bash, not run_step: brew.sh must also work on a Mac without fish.
    echo "==> brew.sh"
    bash brew.sh
    if test $status -ne 0
        echo "Error: brew.sh failed."
        exit 1
    end
    # On the first run the fish configuration is not stowed yet, so this
    # process does not know the Homebrew PATH. Without it, step 2 cannot
    # find stow and step 3 cannot find mise.
    for homebrew_bin_directory in /opt/homebrew/bin /usr/local/bin
        if test -x $homebrew_bin_directory/brew
            fish_add_path -g $homebrew_bin_directory
        end
    end
else if command -q pacman
    run_step paru.fish
else if command -q apt
    run_step apt/ubuntu.fish
    run_step apt/stow.fish
    run_step apt/cargo.fish
    run_step apt/less.fish
    if not command -q fish
        bash fish.sh; or exit 1
    end
else
    echo "Error: neither pacman nor apt was found."
    exit 1
end

# 2. Link the dotfiles, so ~/.config/mise/config.toml exists
run_step ../stow.fish

# 3. Every runtime and CLI tool
run_step mise.fish

# 4. Third-party agent skills for Claude Code, Codex and pi. Downloaded from
# their sources into ~/.agents/skills; needs npx from step 3.
run_step agent-skills.fish

# The AeroSpace tab helper. float-macos-tabs.sh needs it to see which
# windows share one macOS tab group. swiftc comes with the Xcode Command
# Line Tools, which the Homebrew installer already put in place.
if test (uname) = Darwin; and command -q swiftc
    echo "==> aerospace-window-frames"
    swiftc -O -o ~/.local/bin/aerospace-window-frames \
        ../aerospace/.config/aerospace/window-frames.swift
    or echo "Warning: aerospace-window-frames did not build. AeroSpace then tiles macOS tabs."
end

# Rebuild bat cache against the stowed bat config
if command -q bat
    bat cache --build
end

# Git credentials for WSL
if test -e /proc/sys/fs/binfmt_misc/WSLInterop
    git config --global credential.helper "/mnt/c/Program\ Files/Git/mingw64/libexec/git-core/git-credential-wincred.exe"
end

echo "Done."
