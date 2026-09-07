#!/bin/sh
# Move the mouse to the center of the focused window, after AeroSpace has
# applied the layout.
#
# Use this from a key binding with exec-and-forget after a command that
# changes window positions (move, workspace, close, ...). A plain
# 'move-mouse window-lazy-center' in the same binding list would run
# BEFORE the layout, and it would use the old position of the window.
# For a plain focus change (focus left/right/...) the positions do not
# change, so those bindings call move-mouse directly.
#
# The short sleep gives AeroSpace time to finish the layout. Without the
# mouse move, focus-follows-mouse would give the focus back to the window
# under the resting mouse at the next mouse movement.

sleep 0.1
exec aerospace move-mouse window-lazy-center >/dev/null 2>&1
