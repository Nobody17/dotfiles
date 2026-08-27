# Everything above the `status is-interactive` block runs for scripts too:
# every `fish -c` from nvim, git hooks and tooling pays for it. Keep it to
# environment variables and PATH. No subprocesses, no `... | source`.

set -gx ERL_AFLAGS "-kernel shell_history enabled"
set -gxa PHP_INI_SCAN_DIR "$HOME/.config/herd-lite/bin"

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
if test -d "$HOME/Android/Sdk"
    set -gx ANDROID_HOME "$HOME/Android/Sdk"
    set -gx ANDROID_SDK_ROOT "$ANDROID_HOME"
    for dir in platform-tools emulator cmdline-tools/latest/bin
        if test -d "$ANDROID_HOME/$dir"
            fish_add_path -g "$ANDROID_HOME/$dir"
        end
    end
end

# JDK 17 for Gradle (system default is 26, too new for Gradle 8.13 / Expo SDK 53).
# JAVA_HOME only — `java` on PATH stays at the system default.
# jdk17-openjdk comes from paru: mise only offers openjdk-17.0.2, which has
# had no security patches since 2022.
if test -d /usr/lib/jvm/java-17-openjdk
    set -gx JAVA_HOME /usr/lib/jvm/java-17-openjdk
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

    # Start SSH agent if not already running
    if not set -q SSH_AUTH_SOCK
        eval (ssh-agent -c) >/dev/null
    end

    fzf --fish | source
    zoxide init fish | source
    starship init fish | source
    enable_transience

    # mise must be the last PATH modification.
    if type -q mise
        mise activate fish | source
    end
else
    # Scripts get the tool versions through the shims instead, which costs
    # nothing at startup. Per-directory switching still works: each shim
    # resolves the version itself when it runs.
    if test -d "$HOME/.local/share/mise/shims"
        fish_add_path -g --prepend "$HOME/.local/share/mise/shims"
    end
end
