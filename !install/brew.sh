#!/bin/bash

# macOS system layer: Homebrew plus the packages in the Brewfile.
#
# This is a bash script, not a fish script, because a fresh Mac has no fish.
# It is the macOS counterpart of paru.fish (Arch) and fish.sh (Debian).
#
# On a fresh Mac, run these commands from the repository root:
#   bash '!install/brew.sh'
#   exec zsh -l    # or open a new terminal, so zsh reads the new ~/.zprofile
#   fish '!install/install.fish'
#
# install.fish also calls this script, so a second run costs nothing:
# every step below checks its own state first.

set -euo pipefail

script_directory="$(cd "$(dirname "$0")" && pwd)"

if [ "$(uname)" != "Darwin" ]; then
    echo "Error: this script installs Homebrew packages, so it runs on macOS only."
    exit 1
fi

# Apple Silicon keeps Homebrew in /opt/homebrew, Intel in /usr/local.
homebrew_prefix="/opt/homebrew"
if [ "$(uname -m)" != "arm64" ]; then
    homebrew_prefix="/usr/local"
fi

# 1. Homebrew. Its installer also installs the Xcode Command Line Tools,
#    which provide git, make and the C compiler.
if ! command -v brew >/dev/null 2>&1 && [ -x "$homebrew_prefix/bin/brew" ]; then
    # Homebrew is installed, but this shell does not have it on PATH yet.
    eval "$("$homebrew_prefix/bin/brew" shellenv)"
fi

if ! command -v brew >/dev/null 2>&1; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$("$homebrew_prefix/bin/brew" shellenv)"
fi

# Persist the Homebrew PATH for zsh, the macOS login shell. Without this
# line the parent shell cannot find fish after this script ends, and the
# next command from the header above fails. The stowed fish configuration
# covers fish itself later.
zsh_profile="$HOME/.zprofile"
shellenv_line="eval \"\$(\"$homebrew_prefix/bin/brew\" shellenv)\""
if ! grep -qsF "$shellenv_line" "$zsh_profile"; then
    echo "Adding the Homebrew PATH to $zsh_profile ..."
    printf '%s\n' "$shellenv_line" >>"$zsh_profile"
fi

# 2. The packages. --no-upgrade keeps the run fast and predictable:
#    it installs what is missing and never touches what is present.
echo "Installing the Brewfile packages..."
brew bundle --no-upgrade --file="$script_directory/Brewfile"

# 3. rustup owns rust; mise defers to it. The rustup formula is keg-only,
#    so brew does not link it into $homebrew_prefix/bin. After "rustup
#    default stable" the usual proxies appear in ~/.cargo/bin.
rustup_command="rustup"
if ! command -v rustup >/dev/null 2>&1 && [ -x "$homebrew_prefix/opt/rustup/bin/rustup" ]; then
    rustup_command="$homebrew_prefix/opt/rustup/bin/rustup"
fi

if ! "$rustup_command" default >/dev/null 2>&1; then
    echo "Setting the Rust default toolchain..."
    "$rustup_command" default stable
fi

echo "Success: the macOS system layer is complete."
