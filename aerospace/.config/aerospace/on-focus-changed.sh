#!/bin/sh
# The on-focus-changed callback of aerospace.toml.
#
# The order matters: float-macos-tabs.sh decides which windows belong to the
# tiling tree, and dwindle-autotiling.sh then arranges the tree. A single
# script keeps that order; two exec-and-forget entries would race.
#
# The scripts themselves change the focus for a short time (see
# tile_next_to_last_focused_window in float-macos-tabs.sh). Each of those
# focus changes starts this script again. The lock makes the new runs wait
# until the first run is complete, so two runs never work on the tree at
# the same time.
#
# After the scripts, this script records the focused window. The next run
# reads that record: it is the window that had the focus BEFORE the new
# window appeared, and the new window is placed next to it.

lock_directory="${TMPDIR:-/tmp}/aerospace-on-focus-changed.lock"
last_focused_window_file="${TMPDIR:-/tmp}/aerospace-last-focused-window"

# A run that was interrupted can leave the lock behind. A run needs less
# than a second, so a lock older than ten seconds is stale.
remove_stale_lock() {
    [ -d "$lock_directory" ] || return 0
    lock_time="$(stat -f %m "$lock_directory" 2>/dev/null)" || return 0
    lock_age_seconds=$(( $(date +%s) - lock_time ))
    [ "$lock_age_seconds" -gt 10 ] && rmdir "$lock_directory" 2>/dev/null
}

# mkdir is atomic, so only one run can create the lock. Wait up to two
# seconds for the lock, then give up.
wait_attempts=20
until mkdir "$lock_directory" 2>/dev/null; do
    remove_stale_lock
    wait_attempts=$((wait_attempts - 1))
    [ "$wait_attempts" -le 0 ] && exit 0
    sleep 0.1
done
trap 'rmdir "$lock_directory" 2>/dev/null' EXIT

callback_directory="$(dirname "$0")"

"$callback_directory/float-macos-tabs.sh"
"$callback_directory/dwindle-autotiling.sh"

# Record the focused window as "<window-id>|<workspace>". A floating window
# holds no tile, so it is not a place for a split: the record then keeps
# the last tiled window.
focused_window="$(aerospace list-windows --focused \
    --format '%{window-id}|%{workspace}|%{window-layout}')" || exit 0
case "$focused_window" in
    '' | *'|floating') ;;
    *) printf '%s\n' "${focused_window%|*}" >"$last_focused_window_file" ;;
esac
