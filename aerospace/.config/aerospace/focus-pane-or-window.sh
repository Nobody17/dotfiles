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
# The public Herdr API has session-wide focus, while attached clients can
# display different tabs. Never use an untargeted pane focus request here.
# AeroSpace writes a reserved F13-F16 terminal sequence to focused Ghostty. Herdr's
# custom key command calls this script with --from-herdr and supplies
# HERDR_ACTIVE_PANE_ID, HERDR_SOCKET_PATH, and HERDR_BIN_PATH for that client.
# See herdr/.config/herdr/config.toml for the matching bindings.
#
# Session discovery below only identifies Herdr windows; it does not choose
# the pane to operate on. Errors must not masquerade as layout boundaries.

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

# Move between macOS windows only if the originating window still has focus.
focus_window() {
    current_window_id="$(aerospace list-windows --focused --format '%{window-id}' 2>/dev/null)" || return 1
    [ -n "$origin_window_id" ] && [ "$current_window_id" = "$origin_window_id" ] || return 1
    aerospace focus --boundaries all-monitors-outer-frame \
        --boundaries-action wrap-around-all-monitors "$direction" >/dev/null 2>&1 || return 1
    aerospace move-mouse window-lazy-center >/dev/null 2>&1 ||
        aerospace move-mouse monitor-lazy-center >/dev/null 2>&1
}

origin_window_id="$(aerospace list-windows --focused --format '%{window-id}' 2>/dev/null)" || origin_window_id=""
if [ -z "$origin_window_id" ]; then
    # Empty workspaces have no focused window, but must still allow navigation.
    # A delayed pane callback must not navigate after losing its source window.
    [ "${2:-}" != "--from-herdr" ] || exit 1
    origin_workspace="$(aerospace list-workspaces --focused 2>/dev/null)" || exit 1
    [ -n "$origin_workspace" ] || exit 1
    aerospace focus --boundaries all-monitors-outer-frame \
        --boundaries-action wrap-around-all-monitors "$direction" >/dev/null 2>&1 || exit 1
    aerospace move-mouse window-lazy-center >/dev/null 2>&1 ||
        aerospace move-mouse monitor-lazy-center >/dev/null 2>&1
    exit $?
fi

if [ "${2:-}" = "--from-herdr" ]; then
    # Herdr sets these when handling the key in the requesting client. Do not
    # substitute this script's inherited caller pane or the API's global focus.
    [ -n "${HERDR_ACTIVE_PANE_ID:-}" ] && [ -x "${HERDR_BIN_PATH:-}" ] || exit 1
    focus_result="$("$HERDR_BIN_PATH" pane focus --pane "$HERDR_ACTIVE_PANE_ID" \
        --direction "$direction" 2>/dev/null)" || exit 1
    outcome="$(printf '%s' "$focus_result" | jq -r '
        if .result.focus.changed == true then "changed"
        elif .result.focus.changed == false and .result.focus.reason == "no_neighbor"
        then "edge" else "error" end' 2>/dev/null)" || exit 1
    case "$outcome" in
        changed) exit 0 ;;
        edge) focus_window; exit $? ;;
        *) exit 1 ;;
    esac
fi

herdr="$(herdr_binary)"
if [ -n "$herdr" ]; then
    session_of_window="$(herdr_session_of_focused_window)"
    if [ -n "$session_of_window" ]; then
        focused_pid="$(aerospace list-windows --focused --format '%{app-pid}' 2>/dev/null)" || exit 1
        [ "$(aerospace list-windows --focused --format '%{window-id}' 2>/dev/null)" = "$origin_window_id" ] || exit 1
        # Direct terminal bytes preserve the user's held Super/Ctrl/Option keys.
        # Synthetic key events can disturb those modifiers and produce Escape.
        exec osascript -l JavaScript "$(dirname "$0")/send-herdr-focus.js" "$focused_pid" "$direction"
    fi
fi

focus_window
