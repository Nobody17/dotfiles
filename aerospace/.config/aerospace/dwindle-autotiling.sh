#!/bin/sh
# Dwindle autotiling for AeroSpace, like the Hyprland dwindle layout.
#
# AeroSpace puts each new window directly after the focused window, in the
# same container. (For a Ghostty window, which starts floating,
# float-macos-tabs.sh makes sure of that placement.) This script reacts
# only when a NEW window appears: it joins the new window and that
# neighbor into a container with the opposite direction (join-with). So
# the new window always splits the window that had the focus, and the
# splits alternate: horizontal, vertical, horizontal, and so on.
#
# The script runs on each focus change (see on-focus-changed in
# aerospace.toml). It keeps a list of known window ids. A focus change
# to a known window does nothing, so existing windows never move.

known_windows_file="${TMPDIR:-/tmp}/aerospace-dwindle-known-windows"

# The number of lines in a newline separated list of window ids.
count_window_ids() {
    if [ -z "$1" ]; then
        echo 0
    else
        printf '%s\n' "$1" | wc -l | tr -d ' '
    fi
}

focused_window="$(aerospace list-windows --focused \
    --format '%{window-id}|%{window-layout}|%{window-parent-container-layout}|%{window-is-fullscreen}')" || exit 0
all_window_ids="$(aerospace list-windows --all --format '%{window-id}')" || exit 0

focused_window_id="${focused_window%%|*}"
remainder="${focused_window#*|}"
window_layout="${remainder%%|*}"
remainder="${remainder#*|}"
parent_container_layout="${remainder%%|*}"
window_is_fullscreen="${remainder#*|}"

# On the first run, only record the windows that already exist.
if [ ! -f "$known_windows_file" ]; then
    printf '%s\n' "$all_window_ids" >"$known_windows_file"
    exit 0
fi

previous_window_ids="$(cat "$known_windows_file")"
printf '%s\n' "$all_window_ids" >"$known_windows_file"

if printf '%s\n' "$previous_window_ids" | grep -q -x "$focused_window_id"; then
    exit 0
fi

# From here on, the focused window id is unknown.

# An app can replace a window with a new one: the id list then shows an
# unknown id while the total count stays the same. That is not a new
# window, and a join-with would rebuild the split for nothing. Only a
# real new window raises the count.
previous_window_count="$(count_window_ids "$previous_window_ids")"
current_window_count="$(count_window_ids "$all_window_ids")"
[ "$current_window_count" -le "$previous_window_count" ] && exit 0

# A floating window holds no tile, so there is nothing to join. This also
# covers a macOS tab that float-macos-tabs.sh took out of the tree.
[ "$window_layout" = "floating" ] && exit 0

# Only act on tiled windows inside a tiles container. Skip accordions
# and fullscreen windows.
case "$parent_container_layout" in
    h_tiles | v_tiles) ;;
    *) exit 0 ;;
esac
[ "$window_is_fullscreen" = "true" ] && exit 0

# Do not join the first or the second window of a workspace. The first
# split must follow the monitor orientation
# (default-root-container-orientation).
window_count="$(aerospace list-windows --workspace focused --count)"
[ "$window_count" -le 2 ] && exit 0


# Join the new window with its neighbor in the opposite direction of the
# parent container. The neighbor is usually before the new window; if
# not, try the other side.
if [ "$parent_container_layout" = "h_tiles" ]; then
    aerospace join-with --window-id "$focused_window_id" left ||
        aerospace join-with --window-id "$focused_window_id" right
else
    aerospace join-with --window-id "$focused_window_id" up ||
        aerospace join-with --window-id "$focused_window_id" down
fi
