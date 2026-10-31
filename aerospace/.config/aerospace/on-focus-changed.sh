#!/bin/sh
# The on-focus-changed callback of aerospace.toml.
#
# The order matters: float-macos-tabs.sh decides which windows belong to the
# tiling tree, and dwindle-autotiling.sh then arranges the tree. A single
# script keeps that order; two exec-and-forget entries would race.
#
# The scripts themselves change the focus for a short time (see
# tile_next_to_last_focused_window in float-macos-tabs.sh). Each of those
# focus changes starts this script again. One worker owns the layout lock;
# overlapping callbacks request another pass and exit instead of polling.
#
# After the scripts, this script records the focused window. The next run
# reads that record: it is the window that had the focus BEFORE the new
# window appeared, and the new window is placed next to it.

callback_directory="${0%/*}"

# Release native keyboard focus on empty workspaces before waiting for layout
# work. Otherwise macOS keeps typing into the app on the previous monitor.
# Most focus changes are between populated workspaces. Avoid launching the
# JavaScript runtime and Standard Additions just to discover that fact. The
# native-focus helper still rechecks live state before activating anything.
window_count="$(aerospace list-windows --workspace focused --count 2>/dev/null)" || window_count=""
if [ "$window_count" = 0 ]; then
    osascript -l JavaScript "$callback_directory/focus-empty-workspace.js" "$(command -v aerospace)"
fi

lock_directory="${TMPDIR:-/tmp}/aerospace-on-focus-changed.lock"
pending_file="${TMPDIR:-/tmp}/aerospace-on-focus-changed.pending"
last_focused_window_file="${TMPDIR:-/tmp}/aerospace-last-focused-window"

# A killed worker can leave a lock behind. Do not evict a live worker just
# because a continuous stream of focus events kept it busy for ten seconds.
remove_stale_lock() {
    [ -d "$lock_directory" ] || return 0
    if [ -f "$lock_directory/pid" ]; then
        read -r lock_pid <"$lock_directory/pid"
        case "$lock_pid" in
            '' | *[!0-9]*) ;;
            *) kill -0 "$lock_pid" 2>/dev/null && return 0 ;;
        esac
    fi
    lock_time="$(stat -f %m "$lock_directory" 2>/dev/null)" || return 0
    lock_age_seconds=$(( $(date +%s) - lock_time ))
    if [ "$lock_age_seconds" -gt 10 ]; then
        rm -f "$lock_directory/pid"
        rmdir "$lock_directory" 2>/dev/null
    fi
}

release_lock() {
    rm -f "$lock_directory/pid"
    rmdir "$lock_directory" 2>/dev/null
    trap - EXIT
}

acquire_lock() {
    if ! mkdir "$lock_directory" 2>/dev/null; then
        remove_stale_lock
        mkdir "$lock_directory" 2>/dev/null || return 1
    fi
    printf '%s\n' "$$" >"$lock_directory/pid"
    trap release_lock EXIT
}

# Set the marker before competing for ownership. A callback arriving during
# a pass must cause another pass; a callback arriving during release must
# either acquire the lock itself or be picked up by the releasing worker.
: >"$pending_file"
acquire_lock || exit 0
trap 'exit 0' HUP INT TERM

while :; do
    rm -f "$pending_file"

    "$callback_directory/float-macos-tabs.sh"
    "$callback_directory/dwindle-autotiling.sh"

    # Record the focused window as "<window-id>|<workspace>". A floating
    # window holds no tile, so keep the last tiled window as a split target.
    focused_window="$(aerospace list-windows --focused \
        --format '%{window-id}|%{workspace}|%{window-layout}')" || focused_window=""
    case "$focused_window" in
        '' | *'|floating') ;;
        *) printf '%s\n' "${focused_window%|*}" >"$last_focused_window_file" ;;
    esac

    [ -f "$pending_file" ] && continue
    release_lock
    [ -f "$pending_file" ] || exit 0
    acquire_lock || exit 0
done
