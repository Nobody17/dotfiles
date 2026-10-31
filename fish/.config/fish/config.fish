# Docker Desktop installs its commands in the current user's home directory.
if test -d "$HOME/.docker/bin"
    fish_add_path -g --append "$HOME/.docker/bin"
end

# Everything above the `status is-interactive` block runs for scripts too:
# every `fish -c` from nvim, git hooks and tooling pays for it. Keep it to
# environment variables and PATH. No subprocesses, no `... | source`.

set -gx ERL_AFLAGS "-kernel shell_history enabled"
set -gxa PHP_INI_SCAN_DIR "$HOME/.config/herd-lite/bin"

# rustup installs a missing toolchain only on `rustup toolchain install`.
# Without this, any rustup call in a folder with rust-toolchain.toml, or with
# Homebrew's fallback default "stable", downloads about 1.3 GB on its own.
set -gx RUSTUP_AUTO_INSTALL 0

# Homebrew on macOS: /opt/homebrew on Apple Silicon, /usr/local on Intel.
# Static values instead of `brew shellenv | source`, because the rule above
# forbids subprocesses here. cachyos-config.fish does not exist on macOS,
# so ~/.local/bin and ~/.cargo/bin are added here too.
set -l homebrew_prefix
if test -x /opt/homebrew/bin/brew
    set homebrew_prefix /opt/homebrew
    set -gx HOMEBREW_REPOSITORY /opt/homebrew
else if test -x /usr/local/bin/brew
    set homebrew_prefix /usr/local
    set -gx HOMEBREW_REPOSITORY /usr/local/Homebrew
end
if set -q homebrew_prefix[1]
    set -gx HOMEBREW_PREFIX $homebrew_prefix
    set -gx HOMEBREW_CELLAR $homebrew_prefix/Cellar
    fish_add_path -g --prepend $homebrew_prefix/bin $homebrew_prefix/sbin
    fish_add_path -g "$HOME/.local/bin" "$HOME/.cargo/bin"
end

#path
# ~/.local/bin and ~/.cargo/bin are added by cachyos-config.fish below.
fish_add_path -g "$HOME/Programming/software/android-studio/bin/"
fish_add_path -g "$HOME/Programming/software/platform-tools/"
fish_add_path -g "$HOME/.local/share/nvim/mason/bin"
fish_add_path -g "$HOME/go/bin"
fish_add_path -g "$HOME/.config/herd-lite/bin"
fish_add_path -g "$HOME/bin"
fish_add_path -g "$HOME/.local/share/pnpm/bin"
fish_add_path -g --prepend /opt/ffmpeg/bin

# fvm (Flutter Version Management)
if test -d "$HOME/fvm/default/bin"
    fish_add_path -g "$HOME/fvm/default/bin"
end

# Android SDK (React Native / Expo)
if set -q ANDROID_HOME; and test -d "$ANDROID_HOME"
    # Keep an SDK selected by the machine or parent process.
else if test -d "$HOME/Android/Sdk"
    set -gx ANDROID_HOME "$HOME/Android/Sdk"
else if test -d "$HOME/Android/sdk"
    set -gx ANDROID_HOME "$HOME/Android/sdk"
else if test -d "$HOME/Library/Android/sdk"
    set -gx ANDROID_HOME "$HOME/Library/Android/sdk"
else if test -d "/opt/homebrew/share/android-commandlinetools"
    set -gx ANDROID_HOME "/opt/homebrew/share/android-commandlinetools"
end
if set -q ANDROID_HOME
    set -gx ANDROID_SDK_ROOT "$ANDROID_HOME"
    for directory in platform-tools emulator cmdline-tools/latest/bin
        if test -d "$ANDROID_HOME/$directory"
            fish_add_path -g "$ANDROID_HOME/$directory"
        end
    end
end

if status is-interactive
    # Aliases, key bindings and the fastfetch greeting. Also adds
    # ~/.local/bin and ~/.cargo/bin to PATH, and points MANPAGER at bat.
    if test -f /usr/share/cachyos-fish-config/cachyos-config.fish
        source /usr/share/cachyos-fish-config/cachyos-config.fish
    end

    #abbreviations
    abbr -a g -- lazygit
    abbr -a lzd -- lazydocker
    abbr -a l -- eza -lah --git --git-repos --group-directories-first
    abbr -a lts -- eza -lah --git --git-repos --group-directories-first --total-size
    abbr -a n -- nvim
    abbr -a wl --position anywhere -- --UseOzonePlatform --ozone-platform-hint=wayland

    # SSH agent. On macOS launchd sets SSH_AUTH_SOCK to the Apple agent, which
    # cannot hold FIDO (sk) keys from the YubiKey. Replace it with one shared
    # Homebrew agent on a fixed socket, so `ssh-add -K` is needed only once
    # after login, not in every terminal.
    if string match -q '/var/run/com.apple.launchd.*' -- "$SSH_AUTH_SOCK"
        set -l shared_agent_socket "$HOME/.ssh/agent/shared.sock"
        set -gx SSH_AUTH_SOCK $shared_agent_socket
        # Exit code 2 means "cannot connect to the agent"; 0 and 1 mean it runs.
        ssh-add -l >/dev/null 2>&1
        if test $status -eq 2
            mkdir -p -m 700 (dirname $shared_agent_socket)
            rm -f $shared_agent_socket
            ssh-agent -a $shared_agent_socket >/dev/null
        end
    end
    # Linux: start an agent if the session did not provide one.
    if not set -q SSH_AUTH_SOCK
        eval (ssh-agent -c) >/dev/null
    end

    fzf --fish | source
    zoxide init fish | source
    starship init fish | source
    enable_transience

    # mise selects JAVA_HOME and must be the last PATH modification.
    if type -q mise
        mise activate fish | source
    end
else
    # Scripts get the tool versions through the shims instead, which costs
    # nothing at startup. Per-directory switching still works: each shim
    # resolves the version itself when it runs.
    # Use mise exec for scripts that also need JAVA_HOME, such as Gradle.
    if test -d "$HOME/.local/share/mise/shims"
        fish_add_path -g --prepend "$HOME/.local/share/mise/shims"
    end
end
