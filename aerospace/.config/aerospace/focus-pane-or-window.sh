#!/bin/sh
# Move the focus in one direction: first inside Herdr, then across windows
# and monitors with AeroSpace.
#
# Usage:  focus-pane-or-window.sh left|down|up|right
#
# The Super+h/j/k/l bindings in aerospace.toml call this script. AeroSpace
# takes the key before the terminal sees it, so Herdr alone can never
# react to Super+h/j/k/l. This script gives Herdr the first chance:
#
#   1. If the focused window is a Herdr window, ask Herdr to focus the
#      pane in that direction. Herdr answers with "changed": true when a
#      pane took the focus. Then the job is done.
#   2. Otherwise, or when the focused pane sits at the edge of the Herdr
#      layout ("changed": false, "reason": "no_neighbor"), run the normal
#      AeroSpace focus. It continues on the next window, then on the next
#      monitor, and it wraps around at the outer edge, like the bindings
#      did before.
#
# Herdr can run several sessions (herdr --session NAME), each with its own
# server. The script finds the session of the focused window in two steps:
#
#   a. Process tree. It looks for Herdr client processes below the process
#      that owns the window. A client started with "--session NAME" or
#      "session attach NAME" belongs to that session, every other client
#      to the default session. When exactly one session is found, that is
#      the session of the window. This is the precise way, and it covers
#      "ghostty --command=herdr" and Herdr started in a shell.
#   b. Window title. Herdr writes "<hostname>: <workspace>" to the outer
#      terminal (window_title in ~/.config/herdr/config.toml). The script
#      asks each running session for its focused workspace and takes the
#      session whose title matches. This is the fallback when one terminal
#      process owns several windows with different sessions, or when the
#      process tree shows no client.
#
# A window with a remote client (herdr --remote) gets the plain AeroSpace
# focus, because the local CLI cannot reach that server.
#
# mise installs Herdr (see ~/.config/mise/config.toml). AeroSpace starts
# this script with a small PATH without the mise shims, so the script asks
# mise for the Herdr binary. The client must have the same version as the
# server, or it refuses to talk ("protocol_mismatch"); one install through
# mise keeps them equal. Without mise, the script uses "herdr" in PATH.
#
# The mouse follows the focus (focus-follows-mouse in aerospace.toml). A
# pane change inside Herdr keeps the same window, so the mouse can stay
# where it is. A window change moves the mouse to the new window.

direction="$1"
case "$direction" in
    left | down | up | right) ;;
    *)
        echo "Usage: $(basename "$0") left|down|up|right" >&2
        exit 2
        ;;
esac

# Print the command line of every process below the given process id, one
# line each. The window owner is the root; the Herdr client is usually two
# levels down (terminal -> login -> herdr).
descendant_command_lines() {
    root_process_id="$1"
    ps -eo pid=,ppid=,command= 2>/dev/null | awk -v root="$root_process_id" '
        {
            process_id = $1
            parent_of[process_id] = $2
            $1 = ""
            $2 = ""
            command_of[process_id] = substr($0, 3)
        }
        END {
            for (process_id in parent_of) {
                if (process_id == root) continue
                ancestor = parent_of[process_id]
                depth = 0
                while (ancestor != root && (ancestor in parent_of) && depth < 64) {
                    ancestor = parent_of[ancestor]
                    depth++
                }
                if (ancestor == root) print command_of[process_id]
            }
        }'
}

# Read command lines on stdin. For each Herdr client, print its session
# name: the name after --session or "session attach", "remote" for a
# remote client, or "default". Other processes print nothing. The Herdr
# server and the short-lived CLI calls are not clients.
herdr_client_sessions() {
    awk '
        {
            executable = $1
            sub(/^-/, "", executable)   # a login shell exec marks argv[0] with "-"
            if (executable !~ /(^|\/)herdr$/) next

            session_name = "default"
            for (index_of_argument = 2; index_of_argument <= NF; index_of_argument++) {
                argument = $index_of_argument
                if (argument == "--session" && index_of_argument < NF) {
                    session_name = $(index_of_argument + 1)
                } else if (argument ~ /^--session=/) {
                    session_name = substr(argument, 11)
                } else if (argument == "--remote") {
                    session_name = "remote"
                } else if (argument == "session" && $(index_of_argument + 1) == "attach" &&
                           index_of_argument + 2 <= NF) {
                    session_name = $(index_of_argument + 2)
                } else if (index_of_argument == 2 && argument !~ /^-/) {
                    # "herdr server", "herdr pane ...", "herdr status" and so on
                    # are no clients. "herdr session attach NAME" is handled above.
                    if (argument != "session") next
                }
            }
            print session_name
        }' | sort -u
}

# Print the path of the Herdr binary: the mise install, or "herdr" from
# PATH when mise does not know it.
herdr_binary() {
    mise_binary="$(mise which herdr 2>/dev/null)"
    if [ -n "$mise_binary" ] && [ -x "$mise_binary" ]; then
        printf '%s\n' "$mise_binary"
    else
        command -v herdr 2>/dev/null
    fi
}

# Print the names of the running sessions, one per line.
running_sessions() {
    "$herdr" session list --json 2>/dev/null |
        jq -r '.sessions[] | select(.running) | .name' 2>/dev/null
}

# Print the label of the focused workspace of a session.
focused_workspace_label() {
    "$herdr" --session "$1" workspace list 2>/dev/null |
        jq -r '.result.workspaces[] | select(.focused) | .label' 2>/dev/null | head -n 1
}

# Print the session whose focused workspace makes the given window title,
# in the form "<hostname>: <workspace>". Candidate sessions come on stdin;
# an empty stdin means every running session.
session_matching_title() {
    window_title="$1"
    host_name="$(hostname 2>/dev/null)" || return 1
    case "$window_title" in
        "$host_name: "*) ;;
        *) return 1 ;;
    esac
    workspace_label_in_title="${window_title#"$host_name: "}"

    candidate_sessions="$(cat)"
    [ -n "$candidate_sessions" ] || candidate_sessions="$(running_sessions)"

    printf '%s\n' "$candidate_sessions" | while read -r session_name; do
        [ -n "$session_name" ] || continue
        [ "$session_name" = "remote" ] && continue
        if [ "$(focused_workspace_label "$session_name")" = "$workspace_label_in_title" ]; then
            printf '%s\n' "$session_name"
            break
        fi
    done
}

# Print the Herdr session of the focused window. Print nothing when the
# focused window is not a local Herdr window.
herdr_session_of_focused_window() {
    focused_window="$(aerospace list-windows --focused \
        --format '%{app-pid}|%{window-title}' 2>/dev/null)" || return 1
    [ -n "$focused_window" ] || return 1
    focused_process_id="${focused_window%%|*}"
    focused_window_title="${focused_window#*|}"

    client_sessions="$(descendant_command_lines "$focused_process_id" | herdr_client_sessions)"
    if [ "$(printf '%s\n' "$client_sessions" | grep -c .)" -eq 1 ]; then
        [ "$client_sessions" = "remote" ] && return 1
        printf '%s\n' "$client_sessions"
        return 0
    fi

    printf '%s\n' "$client_sessions" | session_matching_title "$focused_window_title"
}

# True when Herdr moved the focus to a pane. False at the edge of the
# layout, when the server is not running, or when the CLI and the server do
# not match: the answer is then not "true", and AeroSpace takes over.
herdr_focused_a_pane() {
    session_name="$1"
    focus_result="$("$herdr" --session "$session_name" pane focus --direction "$direction" 2>/dev/null)" || return 1
    changed="$(printf '%s' "$focus_result" | jq -r '.result.focus.changed // false' 2>/dev/null)"
    [ "$changed" = "true" ]
}

herdr="$(herdr_binary)"
if [ -n "$herdr" ]; then
    session_of_window="$(herdr_session_of_focused_window)"
    if [ -n "$session_of_window" ] && herdr_focused_a_pane "$session_of_window"; then
        exit 0
    fi
fi

aerospace focus --boundaries all-monitors-outer-frame \
    --boundaries-action wrap-around-all-monitors "$direction" >/dev/null 2>&1
exec aerospace move-mouse window-lazy-center >/dev/null 2>&1
