function codex --wraps codex --description 'Start Codex with the current terminal context'
    # A shared Codex server keeps the first client's HERDR_PANE_ID. Its hooks
    # then save other chats against that pane instead of their own panes.
    # Herdr restores chats by typing `codex resume <id>` into this shell too.
    if test "$HERDR_ENV" = 1
        if not contains -- --no-daemon $argv; and \
                not contains -- agents $argv; and \
                not contains -- remote-control $argv; and \
                not string match --quiet --regex '^--remote(=|$)' -- $argv
            command codex --no-daemon $argv
            return $status
        end
    end
    command codex $argv
end
