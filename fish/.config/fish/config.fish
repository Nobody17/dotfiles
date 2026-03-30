source /usr/share/cachyos-fish-config/cachyos-config.fish

function y
	set tmp (mktemp -t "yazi-cwd.XXXXXX")
	command yazi $argv --cwd-file="$tmp"
	if read -z cwd < "$tmp"; and [ "$cwd" != "$PWD" ]; and test -d "$cwd"
		builtin cd -- "$cwd"
	end
	rm -f -- "$tmp"
end

# Set up fzf key bindings
fzf --fish | source
if status is-interactive
  zoxide init fish | source
end
starship init fish | source
enable_transience

set -gx ERL_AFLAGS "-kernel shell_history enabled"
set -gxa ASDF_DATA_DIR "/home/yorunai/.asdf"
fish_add_path "/home/yorunai/.asdf/shims"
fish_add_path "/home/yorunai/bin"

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
# set -gxa SSH_SK_HELPER "/mnt/c/bin/SSH/ssh-sk-helper.exe"
#Linux
# set -gxa SSH_ASKPASS "/usr/bin/ssh-askpass"

#path
fish_add_path "/home/yorunai/Programming/software/android-studio/bin/"
fish_add_path "/home/yorunai/Programming/software/platform-tools/"
fish_add_path "/opt/nvim/bin"
fish_add_path "/home/yorunai/.local/share/nvim/mason/bin"
fish_add_path "/usr/local/go/bin"
fish_add_path "/home/yorunai/go/bin"
fish_add_path "/home/yorunai/.config/herd-lite/bin"
set -gxa PHP_INI_SCAN_DIR "/home/yorunai/.config/herd-lite/bin"


set PATH $PATH /home/yorunai/.local/bin

set -e -g fish_user_paths
fish_add_path -U --prepend /opt/ffmpeg/bin

