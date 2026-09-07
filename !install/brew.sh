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

# 3. fish as the login shell. macOS keeps zsh, so a new Ghostty window would
#    start zsh and none of the stowed fish configuration would run. chpass
#    only accepts a shell that stands in /etc/shells, so register it first.
fish_path="$homebrew_prefix/bin/fish"
if [ -x "$fish_path" ]; then
    if ! grep -qxF "$fish_path" /etc/shells; then
        echo "Adding $fish_path to /etc/shells (needs sudo)..."
        printf '%s\n' "$fish_path" | sudo tee -a /etc/shells >/dev/null
    fi

    current_shell="$(dscl . -read "/Users/$USER" UserShell | awk '{print $2}')"
    if [ "$current_shell" != "$fish_path" ]; then
        echo "Setting the login shell to $fish_path (needs sudo)..."
        sudo chsh -s "$fish_path" "$USER"
        echo "The new login shell starts in the next terminal window."
    fi
fi

# 4. Screen and sleep timeouts. macOS defaults let the display go dark and
#    the machine sleep after a few minutes, which interrupts a long build or
#    a remote session. The system sleep must stay above the display sleep of
#    the same power source, or the machine sleeps before the screen goes
#    dark and the display value has no effect.
battery_display_sleep_minutes=15
battery_system_sleep_minutes=20
adapter_display_sleep_minutes=30
adapter_system_sleep_minutes=60

# One value out of "pmset -g custom", which prints a section per power
# source ("Battery Power:", "AC Power:") and one indented setting per line.
current_power_setting() {
    power_source="$1"
    setting_name="$2"
    pmset -g custom | awk -v section="$power_source:" -v setting="$setting_name" '
        $0 == section { inside_section = 1; next }
        /^[A-Za-z].*:$/ { inside_section = 0 }
        inside_section && $1 == setting { print $2; exit }
    '
}

power_settings_are_current=true
[ "$(current_power_setting "Battery Power" displaysleep)" = "$battery_display_sleep_minutes" ] ||
    power_settings_are_current=false
[ "$(current_power_setting "Battery Power" sleep)" = "$battery_system_sleep_minutes" ] ||
    power_settings_are_current=false
[ "$(current_power_setting "AC Power" displaysleep)" = "$adapter_display_sleep_minutes" ] ||
    power_settings_are_current=false
[ "$(current_power_setting "AC Power" sleep)" = "$adapter_system_sleep_minutes" ] ||
    power_settings_are_current=false

if [ "$power_settings_are_current" = false ]; then
    echo "Setting the screen and sleep timeouts (needs sudo)..."
    sudo pmset -b displaysleep "$battery_display_sleep_minutes" \
                  sleep "$battery_system_sleep_minutes" \
               -c displaysleep "$adapter_display_sleep_minutes" \
                  sleep "$adapter_system_sleep_minutes"
fi

# 5. rustup owns rust; mise defers to it. The rustup formula is keg-only,
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
