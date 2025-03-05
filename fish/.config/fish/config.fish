if status is-interactive
    # Commands to run in interactive sessions can go here

    set -x ZELLIJ_AUTO_EXIT true
    eval (zellij setup --generate-auto-start fish | string collect)
end

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
source ~/.asdf/asdf.fish

set -gx ERL_AFLAGS "-kernel shell_history enabled"

pyenv init - | source

#abbreviations
abbr cd z
abbr g lazygit
abbr l eza -lah --git --git-repos --group-directories-first
abbr lts eza -lah --git --git-repos --group-directories-first --total-size
abbr n nvim

#WSL
#set -gxa SSH_SK_HELPER "/mnt/c/bin/SSH/ssh-sk-helper.exe"
#Linux
set -gxa SSH_ASKPASS "/usr/bin/ssh-askpass"

#path
fish_add_path "/home/yorunai/.config/herd-lite/bin"
set -gxa PHP_INI_SCAN_DIR "/home/yorunai/.config/herd-lite/bin"
