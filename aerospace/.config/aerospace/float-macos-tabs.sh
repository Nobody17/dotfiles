#!/bin/sh
# Keep the windows of a macOS native tab group out of the AeroSpace tiling
# tree, so a new tab does not change the size of the other windows.
#
# On macOS each tab is a window of its own. AeroSpace gives every window a
# tile, so a tab takes space from the workspace although you cannot see it.
# That is why opening or closing a tab resizes everything.
#
# The tabs of one group share one frame, and only the active tab is on
# screen. window-frames.swift reports frames, and this script uses them to
# group the windows. One window of each group stays tiled. It is the anchor:
# it holds the tile of the whole group, and because all tabs of the group
# share the frame, the group follows that tile. Every other window of the
# group becomes floating, which takes it out of the tree.
#
# aerospace.toml makes each new Ghostty window floating before AeroSpace can
# tile it (on-window-detected). This script then tiles the ones that are not
# tabs. Without that order the layout would jump once and come back.

handled_windows_file="${TMPDIR:-/tmp}/aerospace-handled-windows"
tab_floated_windows_file="${TMPDIR:-/tmp}/aerospace-tab-floated-windows"
last_focused_window_file="${TMPDIR:-/tmp}/aerospace-last-focused-window"
window_frames_helper="$HOME/.local/bin/aerospace-window-frames"

# Give a window a tile next to the window that had the focus before it.
#
# AeroSpace puts a window that changes from floating to tiling after the
# most recent window of its workspace. For a new Ghostty window the most
# recent window is the new window itself, and it is floating. AeroSpace
# then falls back to the end of the root container, far from the window
# that you worked in. A short focus on the last focused window (recorded
# by on-focus-changed.sh) makes that window the most recent one, so the
# new window lands directly next to it. dwindle-autotiling.sh then joins
# the two into a split. The focus goes back at the end.
#
# on-focus-changed.sh holds a lock while this runs, so the two focus
# changes here do not start a second run at the same time.
tile_next_to_last_focused_window() {
    window_identifier="$1"

    [ -f "$last_focused_window_file" ] || {
        aerospace layout tiling --window-id "$window_identifier" >/dev/null 2>&1
        return
    }
    last_focused_window="$(cat "$last_focused_window_file")"
    last_focused_window_id="${last_focused_window%%|*}"
    last_focused_workspace="${last_focused_window#*|}"

    # The last focused window must still exist, hold a tile, and be on the
    # workspace of the new window. Otherwise the plain AeroSpace placement
    # is the best that is possible.
    window_workspace="$(aerospace list-windows --all --format '%{window-id}|%{workspace}' |
        grep -x "$window_identifier|.*" | cut -d '|' -f 2)"
    last_focused_window_layout="$(aerospace list-windows --workspace "$last_focused_workspace" \
        --format '%{window-id}|%{window-layout}' 2>/dev/null |
        grep -x "$last_focused_window_id|.*" | cut -d '|' -f 2)"
    if [ "$last_focused_window_id" = "$window_identifier" ] ||
        [ -z "$window_workspace" ] ||
        [ "$window_workspace" != "$last_focused_workspace" ] ||
        [ -z "$last_focused_window_layout" ] ||
        [ "$last_focused_window_layout" = "floating" ]; then
        aerospace layout tiling --window-id "$window_identifier" >/dev/null 2>&1
        return
    fi

    focused_window_id="$(aerospace list-windows --focused --format '%{window-id}')"
    aerospace focus --window-id "$last_focused_window_id" >/dev/null 2>&1
    aerospace layout tiling --window-id "$window_identifier" >/dev/null 2>&1
    layout_status=$?
    [ -n "$focused_window_id" ] &&
        aerospace focus --window-id "$focused_window_id" >/dev/null 2>&1
    return "$layout_status"
}

visible_windows="$(aerospace list-windows --monitor all --workspace visible \
    --format '%{window-id}|%{window-layout}')" || exit 0
[ -n "$visible_windows" ] || exit 0

# Without the helper each window becomes a group of its own. The script then
# only tiles new floating windows, which is the plain AeroSpace behaviour.
# That is better than leaving every Ghostty window floating.
window_frames=""
if [ -x "$window_frames_helper" ]; then
    window_frames="$("$window_frames_helper" 2>/dev/null)" || window_frames=""
fi

# On the first run, only record the windows that already exist. Without
# this, a window that is floating now would count as new and get a tile.
if [ ! -f "$handled_windows_file" ]; then
    printf '%s\n' "$visible_windows" | sed 's/|.*//' | sort -u >"$handled_windows_file"
    exit 0
fi

# Track automatic tab floats separately from handled windows. When a tab
# loses its anchor or becomes an independent window, it needs its tile back.
# Existing manual floats are not owned by this helper.
layout_commands="$(
    {
        sed 's/^/handled /' "$handled_windows_file"
        [ ! -f "$tab_floated_windows_file" ] ||
            sed 's/^/tab-floated /' "$tab_floated_windows_file"
        printf '%s\n' "$visible_windows" | sed 's/^/visible /'
        if [ -n "$window_frames" ]; then
            printf '%s\n' "$window_frames" | sed 's/^/frame /'
        fi
    } | awk '
$1 == "handled" { handled_windows[$2] = 1; next }
$1 == "tab-floated" { tab_floated_windows[$2] = 1; next }

$1 == "visible" {
    split($2, fields, "|")
    identifier = fields[1]
    window_layout[identifier] = fields[2]
    visible_identifiers[++visible_count] = identifier
    next
}

# frame <window-id> <process-id> <x> <y> <width> <height> <is-on-screen>
$1 == "frame" {
    frame_key[$2] = $3 ":" $4 ":" $5 ":" $6 ":" $7
    is_on_screen[$2] = $8
    next
}

END {
    for (position = 1; position <= visible_count; position++) {
        identifier = visible_identifiers[position]
        if (identifier in frame_key && is_on_screen[identifier] == 1)
            on_screen_count[frame_key[identifier]]++
    }
    for (position = 1; position <= visible_count; position++) {
        identifier = visible_identifiers[position]
        # Covered independent windows are also on screen. Equal bounds
        # alone are not evidence of tabs; exactly one member must be visible.
        key = (identifier in frame_key && on_screen_count[frame_key[identifier]] == 1) \
            ? frame_key[identifier] : ("alone:" identifier)
        group_members[key] = group_members[key] " " identifier
    }

    for (key in group_members) {
        member_count = split(group_members[key], members, " ")

        smallest_tiled_identifier = ""
        smallest_identifier = ""
        on_screen_identifier = ""
        group_has_unhandled_window = 0
        group_has_orphaned_tab = 0

        for (position = 1; position <= member_count; position++) {
            identifier = members[position]
            if (smallest_identifier == "" || identifier + 0 < smallest_identifier + 0)
                smallest_identifier = identifier
            if (window_layout[identifier] != "floating" &&
                (smallest_tiled_identifier == "" ||
                 identifier + 0 < smallest_tiled_identifier + 0))
                smallest_tiled_identifier = identifier
            if (is_on_screen[identifier] == 1 && on_screen_identifier == "")
                on_screen_identifier = identifier
            if (!(identifier in handled_windows))
                group_has_unhandled_window = 1
            if (identifier in tab_floated_windows && is_on_screen[identifier] == 1)
                group_has_orphaned_tab = 1
        }

        # Keep the window that already holds the tile. It never changes
        # while you switch tabs, so the group never moves.
        anchor_identifier = smallest_tiled_identifier

        # No member holds a tile. A group of tabs always needs an anchor.
        # Restore a single visible tab that lost its anchor. Without frame
        # evidence, leave known floating tabs alone until the helper recovers.
        if (anchor_identifier == "" && (member_count > 1 || group_has_unhandled_window || group_has_orphaned_tab)) {
            anchor_identifier = (on_screen_identifier != "") \
                ? on_screen_identifier : smallest_identifier
            print "tiling", anchor_identifier
        }

        for (position = 1; position <= member_count; position++) {
            identifier = members[position]
            if (identifier == anchor_identifier) {
                # Ordinary tiles have no automatic float to forget. Emitting
                # this for every tile caused a sed + mv pair per window on
                # every focus change, even when the layout never changed.
                if (window_layout[identifier] != "floating" && identifier in tab_floated_windows)
                    print "forget", identifier
            } else if (member_count > 1) {
                if (window_layout[identifier] != "floating")
                    print "floating", identifier
                else if (!(identifier in handled_windows) || identifier in tab_floated_windows)
                    print "remember", identifier
            }
        }
    }
}
')"

# on-focus-changed.sh serializes callers. Commit state only after successful
# layout changes, so a failed restore can be retried on the next focus event.
if [ -f "$tab_floated_windows_file" ]; then
    cat "$tab_floated_windows_file" >"$tab_floated_windows_file.new"
else
    : >"$tab_floated_windows_file.new"
fi
forget_tab_float() {
    sed "/^$window_identifier\$/d" "$tab_floated_windows_file.new" >"$tab_floated_windows_file.next" &&
        mv "$tab_floated_windows_file.next" "$tab_floated_windows_file.new"
}
printf '%s\n' "$layout_commands" | while read -r target_layout window_identifier; do
    [ -n "$window_identifier" ] || continue
    if [ "$target_layout" = "tiling" ]; then
        tile_next_to_last_focused_window "$window_identifier" && forget_tab_float
    elif [ "$target_layout" = "forget" ]; then
        forget_tab_float
    elif [ "$target_layout" = "remember" ]; then
        printf '%s\n' "$window_identifier" >>"$tab_floated_windows_file.new"
    elif aerospace layout "$target_layout" --window-id "$window_identifier" >/dev/null 2>&1; then
        printf '%s\n' "$window_identifier" >>"$tab_floated_windows_file.new"
    fi
done
sort -u "$tab_floated_windows_file.new" >"$tab_floated_windows_file" &&
    rm "$tab_floated_windows_file.new"

# Remember every window that has a layout now, as a union with the old list.
# A window on a hidden workspace must not lose its entry, or a float that you
# made yourself would come back tiled.
{
    cat "$handled_windows_file"
    printf '%s\n' "$visible_windows" | sed 's/|.*//'
} | sort -u >"$handled_windows_file.new" && mv "$handled_windows_file.new" "$handled_windows_file"
