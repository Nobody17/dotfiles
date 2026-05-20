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
fish_add_path "$ASDF_DATA_DIR/bin"
fish_add_path "$ASDF_DATA_DIR/shims"

# 4. Source asdf (Standard way for Fish)
if test -f "$ASDF_DATA_DIR/asdf.fish"
    source "$ASDF_DATA_DIR/asdf.fish"
end

# Start SSH agent if not already running
if not set -q SSH_AUTH_SOCK
    eval (ssh-agent -c) > /dev/null
end

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

set -e -g fish_user_paths
set -gxa PHP_INI_SCAN_DIR "$HOME/.config/herd-lite/bin"

#path
fish_add_path "$HOME/Programming/software/android-studio/bin/"
fish_add_path "$HOME/Programming/software/platform-tools/"
fish_add_path "/opt/nvim/bin"
fish_add_path "$HOME/.local/share/nvim/mason/bin"
fish_add_path "/usr/local/go/bin"
fish_add_path "$HOME/go/bin"
fish_add_path "$HOME/.config/herd-lite/bin"
fish_add_path "$HOME/bin"
fish_add_path "$HOME/.local/bin"
fish_add_path $HOME/.cargo/bin

# pnpm global bin
if command -v pnpm > /dev/null
    fish_add_path (pnpm bin -g 2>/dev/null || echo "$HOME/.local/share/pnpm")
end

fish_add_path -U --prepend /opt/ffmpeg/bin
