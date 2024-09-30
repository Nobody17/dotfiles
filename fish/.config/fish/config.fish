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
