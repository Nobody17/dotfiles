if grep -q "cachyos" /etc/os-release 2>/dev/null
  source /usr/share/cachyos-fish-config/cachyos-config.fish
end

function y
	set tmp (mktemp -t "yazi-cwd.XXXXXX")
	command yazi $argv --cwd-file="$tmp"
	if read -z cwd < "$tmp"; and [ "$cwd" != "$PWD" ]; and test -d "$cwd"
		builtin cd -- "$cwd"
	end
	rm -f -- "$tmp"
end

fzf --fish | source
if status is-interactive
  zoxide init fish | source
end
starship init fish | source
enable_transience
set -gx ERL_AFLAGS "-kernel shell_history enabled"

set -gx ASDF_DATA_DIR "$HOME/.asdf"
fish_add_path -g "$ASDF_DATA_DIR/bin"
fish_add_path -g "$ASDF_DATA_DIR/shims"

# 4. Source asdf (Standard way for Fish)
if test -f "$ASDF_DATA_DIR/asdf.fish"
    source "$ASDF_DATA_DIR/asdf.fish"
end



# Start SSH agent if not already running
if not set -q SSH_AUTH_SOCK
    eval (ssh-agent -c) > /dev/null
end

set -gx PYENV_ROOT "$HOME/.pyenv"
pyenv init - | source

#abbreviations
abbr -a g -- lazygit
abbr -a lzd -- lazydocker
abbr -a l -- eza -lah --git --git-repos --group-directories-first
abbr -a lts -- eza -lah --git --git-repos --group-directories-first --total-size
abbr -a n -- nvim
abbr -a wl --position anywhere -- --UseOzonePlatform --ozone-platform-hint=wayland

alias get_idf=". $HOME/esp/esp-idf/export.fish"

#WSL
#set -gxa SSH_SK_HELPER "/mnt/c/bin/SSH/ssh-sk-helper.exe"
#Linux
#set -gxa SSH_ASKPASS "/usr/bin/ssh-askpass"

set -gxa PHP_INI_SCAN_DIR "$HOME/.config/herd-lite/bin"

#path
fish_add_path -g "$HOME/Programming/software/android-studio/bin/"
fish_add_path -g "$HOME/Programming/software/platform-tools/"
fish_add_path -g "/opt/nvim/bin"
fish_add_path -g "$HOME/.local/share/nvim/mason/bin"
fish_add_path -g "/usr/local/go/bin"
fish_add_path -g "$HOME/go/bin"
fish_add_path -g "$HOME/.config/herd-lite/bin"
fish_add_path -g "$HOME/bin"
fish_add_path -g "$HOME/.local/bin"
fish_add_path -g $HOME/.cargo/bin

# fvm (Flutter Version Management)
if command -v fvm > /dev/null
    fish_add_path -g "$HOME/fvm/default/bin"
end

# pnpm global bin
if command -v pnpm > /dev/null
    fish_add_path -g (pnpm bin -g 2>/dev/null || echo "$HOME/.local/share/pnpm")
end

fish_add_path -g --prepend /opt/ffmpeg/bin

# pnpm
set -gx PNPM_HOME "$HOME/.local/share/pnpm"
if not string match -q -- "$PNPM_HOME/bin" $PATH
  set -gx PATH "$PNPM_HOME/bin" $PATH
end
# pnpm end

# bun
set --export BUN_INSTALL "$HOME/.bun"
set --export PATH $BUN_INSTALL/bin $PATH


if type -q mise
  mise activate fish | source
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
if test -d /usr/lib/jvm/java-17-openjdk
    set -gx JAVA_HOME /usr/lib/jvm/java-17-openjdk
end
