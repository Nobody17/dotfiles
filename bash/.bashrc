# Environment for bash. The interactive shell is fish; bash runs scripts and
# the Bash tool of Claude Code (CLAUDE_CODE_SHELL in config.fish).
#
# Claude Code makes its shell snapshot with `bash -c -l`, so bash reads
# ~/.bash_profile, which sources this file. The snapshot then sources this
# file a second time. Each step here must therefore be safe to repeat.
#
# Keep this file in step with the part of fish/.config/fish/config.fish above
# `status is-interactive`. Same rule as there: only environment variables and
# PATH, no subprocesses, outside the interactive block at the end.

# path_prepend moves each folder that exists to the front of PATH. A folder
# that is already in PATH moves too: on macOS, /etc/profile runs path_helper
# for login shells, and path_helper pushes /usr/bin and /bin in front of the
# Homebrew and mise folders that the parent fish exported.
path_prepend() {
    local folder
    for folder in "$@"; do
        [ -d "$folder" ] || continue
        PATH=":$PATH:"
        PATH="${PATH//:$folder:/:}"
        PATH="${PATH#:}"
        PATH="${PATH%:}"
        PATH="$folder${PATH:+:$PATH}"
    done
    export PATH
}

# path_append adds each folder that exists to the end of PATH, once.
path_append() {
    local folder
    for folder in "$@"; do
        [ -d "$folder" ] || continue
        case ":$PATH:" in
            *":$folder:"*) ;;
            *) PATH="${PATH:+$PATH:}$folder" ;;
        esac
    done
    export PATH
}

path_append "$HOME/.docker/bin"

export ERL_AFLAGS="-kernel shell_history enabled"
case ":${PHP_INI_SCAN_DIR:-}:" in
    *":$HOME/.config/herd-lite/bin:"*) ;;
    *) export PHP_INI_SCAN_DIR="${PHP_INI_SCAN_DIR:+$PHP_INI_SCAN_DIR:}$HOME/.config/herd-lite/bin" ;;
esac

# See config.fish: stops rustup from downloading a toolchain on its own.
export RUSTUP_AUTO_INSTALL=0

path_append \
    "$HOME/Programming/software/android-studio/bin" \
    "$HOME/Programming/software/platform-tools" \
    "$HOME/.local/share/nvim/mason/bin" \
    "$HOME/go/bin" \
    "$HOME/.config/herd-lite/bin" \
    "$HOME/bin" \
    "$HOME/.local/share/pnpm/bin" \
    "$HOME/fvm/default/bin"

# Homebrew on macOS: /opt/homebrew on Apple Silicon, /usr/local on Intel.
# Static values instead of `eval "$(brew shellenv)"`, as in config.fish.
if [ -x /opt/homebrew/bin/brew ]; then
    export HOMEBREW_PREFIX=/opt/homebrew
    export HOMEBREW_REPOSITORY=/opt/homebrew
elif [ -x /usr/local/bin/brew ]; then
    export HOMEBREW_PREFIX=/usr/local
    export HOMEBREW_REPOSITORY=/usr/local/Homebrew
fi
if [ -n "${HOMEBREW_PREFIX:-}" ]; then
    export HOMEBREW_CELLAR="$HOMEBREW_PREFIX/Cellar"
    path_prepend "$HOMEBREW_PREFIX/sbin" "$HOMEBREW_PREFIX/bin"
fi
path_prepend "$HOME/.cargo/bin" "$HOME/.local/bin" /opt/ffmpeg/bin

# Android SDK (React Native / Expo)
if [ -d "$HOME/Library/Android/sdk" ]; then
    export ANDROID_HOME="$HOME/Library/Android/sdk"
elif [ -d /opt/homebrew/share/android-commandlinetools ]; then
    export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
fi
if [ -n "${ANDROID_HOME:-}" ]; then
    export ANDROID_SDK_ROOT="$ANDROID_HOME"
    path_append \
        "$ANDROID_HOME/platform-tools" \
        "$ANDROID_HOME/emulator" \
        "$ANDROID_HOME/cmdline-tools/latest/bin"
fi

# JDK 17 for Gradle, through JAVA_HOME only. See config.fish.
if [ -d /usr/lib/jvm/java-17-openjdk ]; then
    export JAVA_HOME=/usr/lib/jvm/java-17-openjdk
elif [ -d /Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home ]; then
    export JAVA_HOME=/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home
fi

# mise must be the last PATH change.
case $- in
    *i*)
        if command -v mise >/dev/null 2>&1; then
            eval "$(mise activate bash)"
        fi
        ;;
    *)
        # Scripts and the Claude Code Bash tool use the shims. Each shim picks
        # the tool version of the current folder when it runs.
        path_prepend "$HOME/.local/share/mise/shims"
        ;;
esac
