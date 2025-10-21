#if status is-interactive
#    # Commands to run in interactive sessions can go here
#
#    set -x ZELLIJ_AUTO_EXIT true
#    eval (zellij setup --generate-auto-start fish | string collect)
#end

function y
    set tmp (mktemp -t "yazi-cwd.XXXXXX")
    yazi $argv --cwd-file="$tmp"
    if set cwd (command cat -- "$tmp"); and [ -n "$cwd" ]; and [ "$cwd" != "$PWD" ]
        builtin cd -- "$cwd"
    end
    rm -f -- "$tmp"
end

# Set up fzf key bindings
fzf --fish | source
zoxide init fish | source
starship init fish | source
enable_transience

set -gx ERL_AFLAGS "-kernel shell_history enabled"
set -gxa ASDF_DATA_DIR "/home/yorunai/.asdf"
fish_add_path "/home/yorunai/.asdf/shims"
fish_add_path "/home/yorunai/bin"

pyenv init - | source

#abbreviations
abbr cd z
abbr g lazygit
abbr lzd lazydocker
abbr l eza -lah --git --git-repos --group-directories-first
abbr lts eza -lah --git --git-repos --group-directories-first --total-size
abbr n nvim

#WSL
set -gxa SSH_SK_HELPER "/mnt/c/bin/SSH/ssh-sk-helper.exe"
#Linux
#set -gxa SSH_ASKPASS "/usr/bin/ssh-askpass"

#path
fish_add_path "/usr/local/go/bin"
fish_add_path "/home/yorunai/go/bin"
fish_add_path "/home/yorunai/.config/herd-lite/bin"
set -gxa PHP_INI_SCAN_DIR "/home/yorunai/.config/herd-lite/bin"

