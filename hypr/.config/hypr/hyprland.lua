-- Hyprland 0.55+ Lua config.
-- Main file lives in the dotfiles repo and is symlinked from ~/.config/hypr/hyprland.lua.

local home = os.getenv("HOME") or ""
local configHome = os.getenv("XDG_CONFIG_HOME") or (home .. "/.config")
local hyprConfigDir = configHome .. "/hypr"

local function loadLocalConfig(fileName)
    local path = hyprConfigDir .. "/" .. fileName
    local file = io.open(path, "r")
    if file == nil then
        return
    end
    file:close()

    local ok, err = pcall(dofile, path)
    if not ok then
        print("[hyprland.lua] Failed to load " .. path .. ": " .. tostring(err))
    end
end

-- Machine-specific config kept next to the symlink, not in the dotfiles repo.
loadLocalConfig("monitors.lua")
loadLocalConfig("devices.lua")


---------------------
---- MY PROGRAMS ----
---------------------

local terminal = "kitty"
local terminalCurrentCWD = [=[bash -c 'kitty --directory "$(readlink /proc/$(pgrep -P $(hyprctl activewindow -j | jq .pid) | tail -n 1)/cwd)"']=]
local fileManager = terminal .. [=[ fish -i -c "y; fish"]=]
local menu = "hyprlauncher"
local browser = "firefox"
local gaming = [=[pkill -0 steam && hyprctl clients | grep -q "steam" || (pkill -9 steam; steam)]=]


-------------------
---- AUTOSTART ----
-------------------

hl.on("hyprland.start", function()
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP")
    hl.exec_cmd("systemctl --user enable --now hyprpolkitagent.service")
    hl.exec_cmd("waybar & hyprpaper")
end)


-------------------------------
---- ENVIRONMENT VARIABLES ----
-------------------------------

hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")

-- QT
hl.env("QT_QPA_PLATFORMTHEME", "qt6ct")
hl.env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
hl.env("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
hl.env("QT_STYLE_OVERRIDE", "kvantum")

-- Toolkit Backend Variables
hl.env("GDK_BACKEND", "wayland,x11,*")
hl.env("SDL_VIDEODRIVER", "wayland,x11")
hl.env("CLUTTER_BACKEND", "wayland")

-- XDG Specifications
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_TYPE", "wayland")
hl.env("XDG_SESSION_DESKTOP", "Hyprland")

-- Nvidia
hl.env("LIBVA_DRIVER_NAME", "nvidia")
hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")

hl.env("STEAM_COMPAT_LAUNCHER_SERVICE_HANDLER", home .. "/.local/bin/steam-wrapper")


-----------------------
---- LOOK AND FEEL ----
-----------------------

hl.config({
    general = {
        gaps_in = 4,
        gaps_out = 12,
        border_size = 2,

        col = {
            active_border = { colors = { "rgba(33ccffee)", "rgba(00ff99ee)" }, angle = 45 },
            inactive_border = "rgba(595959aa)",
        },

        resize_on_border = false,
        allow_tearing = false,
        layout = "dwindle",
    },

    decoration = {
        rounding = 5,
        rounding_power = 2,
        active_opacity = 1.0,
        inactive_opacity = 1.0,

        shadow = {
            enabled = true,
            range = 4,
            render_power = 3,
            color = "rgba(1a1a1aee)",
        },

        blur = {
            enabled = false,
            size = 3,
            passes = 1,
            vibrancy = 0.1696,
        },
    },

    animations = {
        enabled = true,
    },
})

-- Curves and animations.
hl.curve("easeOutQuint",   { type = "bezier", points = { { 0.23, 1 },    { 0.32, 1 }   } })
hl.curve("easeInOutCubic", { type = "bezier", points = { { 0.65, 0.05 }, { 0.36, 1 }   } })
hl.curve("linear",         { type = "bezier", points = { { 0, 0 },       { 1, 1 }      } })
hl.curve("almostLinear",   { type = "bezier", points = { { 0.5, 0.5 },   { 0.75, 1 }   } })
hl.curve("quick",          { type = "bezier", points = { { 0.15, 0 },    { 0.1, 1 }    } })

hl.animation({ leaf = "global",        enabled = true, speed = 10,   bezier = "default" })
hl.animation({ leaf = "border",        enabled = true, speed = 5.39, bezier = "easeOutQuint" })
hl.animation({ leaf = "windows",       enabled = true, speed = 4.79, bezier = "easeOutQuint" })
hl.animation({ leaf = "windowsIn",     enabled = true, speed = 4.1,  bezier = "easeOutQuint", style = "popin 87%" })
hl.animation({ leaf = "windowsOut",    enabled = true, speed = 1.49, bezier = "linear",       style = "popin 87%" })
hl.animation({ leaf = "fadeIn",        enabled = true, speed = 1.73, bezier = "almostLinear" })
hl.animation({ leaf = "fadeOut",       enabled = true, speed = 1.46, bezier = "almostLinear" })
hl.animation({ leaf = "fade",          enabled = true, speed = 3.03, bezier = "quick" })
hl.animation({ leaf = "layers",        enabled = true, speed = 3.81, bezier = "easeOutQuint" })
hl.animation({ leaf = "layersIn",      enabled = true, speed = 4,    bezier = "easeOutQuint", style = "fade" })
hl.animation({ leaf = "layersOut",     enabled = true, speed = 1.5,  bezier = "linear",       style = "fade" })
hl.animation({ leaf = "fadeLayersIn",  enabled = true, speed = 1.79, bezier = "almostLinear" })
hl.animation({ leaf = "fadeLayersOut", enabled = true, speed = 1.39, bezier = "almostLinear" })
hl.animation({ leaf = "workspaces",    enabled = true, speed = 1.94, bezier = "almostLinear", style = "fade" })
hl.animation({ leaf = "workspacesIn",  enabled = true, speed = 1.21, bezier = "almostLinear", style = "fade" })
hl.animation({ leaf = "workspacesOut", enabled = true, speed = 1.94, bezier = "almostLinear", style = "fade" })
hl.animation({ leaf = "zoomFactor",    enabled = true, speed = 7,    bezier = "quick" })

hl.config({
    dwindle = {
        preserve_split = true,
    },

    master = {
        new_status = "master",
    },

    misc = {
        force_default_wallpaper = -1,
        disable_hyprland_logo = false,
    },

    input = {
        kb_layout = "de",
        follow_mouse = 1,
        numlock_by_default = true,
        accel_profile = "flat",

        touchpad = {
            natural_scroll = false,
        },
    },
})

hl.gesture({
    fingers = 3,
    direction = "horizontal",
    action = "workspace",
})


---------------------------------------
---- SPLIT MONITOR WORKSPACE SETUP ----
---------------------------------------

local workspaceCount = 10

-- Requires the Lua package at ~/.config/hypr/plugins/split-monitor-workspaces.
-- Install with:
--   git clone https://github.com/zjeffer/split-monitor-workspaces ~/.config/hypr/plugins/split-monitor-workspaces
package.path = package.path
    .. ";" .. hyprConfigDir .. "/?.lua"
    .. ";" .. hyprConfigDir .. "/?/init.lua"

local splitWorkspaces = require("plugins.split-monitor-workspaces")
splitWorkspaces.setup({
    workspace_count = workspaceCount,
    -- split-monitor-workspaces still matches these by Hyprland output name.
    monitor_priority = { "DP-3", "DP-2" },
    keep_focused = true,
    enable_notifications = false,
    enable_persistent_workspaces = true,
    enable_wrapping = true,
    link_monitors = false,
})


---------------------
---- KEYBINDINGS ----
---------------------

local mainMod = "SUPER"

hl.bind(mainMod .. " + A", hl.dsp.exec_cmd(terminalCurrentCWD))
hl.bind(mainMod .. " + SHIFT + A", hl.dsp.exec_cmd(terminal))
hl.bind(mainMod .. " + D", hl.dsp.window.close())
hl.bind(mainMod .. " + M", hl.dsp.exec_cmd("command -v hyprshutdown >/dev/null 2>&1 && hyprshutdown || hyprctl dispatch 'hl.dsp.exit()'"))
hl.bind(mainMod .. " + E", hl.dsp.exec_cmd(fileManager))
hl.bind(mainMod .. " + F", hl.dsp.window.fullscreen())
hl.bind(mainMod .. " + R", hl.dsp.exec_cmd(menu))
hl.bind(mainMod .. " + G", hl.dsp.exec_cmd(browser))
hl.bind(mainMod .. " + O", hl.dsp.exec_cmd(gaming))

-- Move focus with mainMod + vim keys.
hl.bind(mainMod .. " + h", hl.dsp.focus({ direction = "left" }))
hl.bind(mainMod .. " + l", hl.dsp.focus({ direction = "right" }))
hl.bind(mainMod .. " + k", hl.dsp.focus({ direction = "up" }))
hl.bind(mainMod .. " + j", hl.dsp.focus({ direction = "down" }))

-- Move the active window between monitors.
hl.bind(mainMod .. " + CTRL + h", hl.dsp.window.move({ monitor = "-1", follow = true }))
hl.bind(mainMod .. " + CTRL + l", hl.dsp.window.move({ monitor = "+1", follow = true }))
hl.bind(mainMod .. " + CTRL + p", splitWorkspaces.grab_rogue_windows())

-- Switch workspaces with mainMod + [0-9].
-- Move active window to a workspace with mainMod + SHIFT + [0-9].
for workspace = 1, workspaceCount do
    local key = tostring(workspace % workspaceCount)
    local workspaceName = tostring(workspace)
    hl.bind(mainMod .. " + " .. key, splitWorkspaces.workspace(workspaceName))
    hl.bind(mainMod .. " + SHIFT + " .. key, splitWorkspaces.move_to_workspace(workspaceName))
end

-- Example special workspace (scratchpad):
-- hl.bind(mainMod .. " + S", splitWorkspaces.workspace("special:magic"))
-- hl.bind(mainMod .. " + SHIFT + S", splitWorkspaces.move_to_workspace("special:magic"))

-- Scroll through existing workspaces.
hl.bind(mainMod .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }))
hl.bind(mainMod .. " + mouse_up", hl.dsp.focus({ workspace = "e-1" }))

-- Move/resize windows with mainMod + LMB/RMB and dragging.
hl.bind(mainMod .. " + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind(mainMod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- Multimedia keys.
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"), { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), { locked = true, repeating = true })
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true, repeating = true })
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), { locked = true, repeating = true })
hl.bind("XF86MonBrightnessUp", hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%+"), { locked = true, repeating = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%-"), { locked = true, repeating = true })

-- Requires playerctl.
hl.bind("XF86AudioNext", hl.dsp.exec_cmd("playerctl next"), { locked = true })
hl.bind("XF86AudioPause", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioPlay", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioPrev", hl.dsp.exec_cmd("playerctl previous"), { locked = true })


--------------------------------
---- WINDOWS AND WORKSPACES ----
--------------------------------

hl.window_rule({
    name = "suppress-maximize-events",
    match = { class = ".*" },
    suppress_event = "maximize",
})

hl.window_rule({
    name = "fix-xwayland-drags",
    match = {
        class = "^$",
        title = "^$",
        xwayland = true,
        float = true,
        fullscreen = false,
        pin = false,
    },
    no_focus = true,
})

hl.window_rule({
    name = "move-hyprland-run",
    match = { class = "hyprland-run" },
    move = "20 monitor_h-120",
    float = true,
})
