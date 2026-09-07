# Everything above the `status is-interactive` block runs for scripts too:
# every `fish -c` from nvim, git hooks and tooling pays for it. Keep it to
# environment variables and PATH. No subprocesses, no `... | source`.

set -gx ERL_AFLAGS "-kernel shell_history enabled"
set -gxa PHP_INI_SCAN_DIR "$HOME/.config/herd-lite/bin"

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
if test -d "/opt/homebrew/share/android-commandlinetools"
    set -gx ANDROID_HOME "/opt/homebrew/share/android-commandlinetools"
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
else if test -d /Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home
    # macOS: the temurin@17 cask from the Brewfile installs to this path.
    set -gx JAVA_HOME /Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home
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
