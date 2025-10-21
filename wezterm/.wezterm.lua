-- Pull in the wezterm API
local wezterm = require("wezterm")
local mux = wezterm.mux

-- This will hold the configuration.
local config = wezterm.config_builder()

-- This is where you actually apply your config choices

function get_random_entry(tbl)
	local keys = {}
	for key, _ in ipairs(tbl) do
		table.insert(keys, key)
	end
	local randomKey = keys[math.random(1, #keys)]
	return tbl[randomKey]
end

-- For example, changing the color scheme:
config.color_scheme = "Catppuccin Mocha"

if wezterm.target_triple == "x86_64-pc-windows-msvc" then
	-- config.default_cwd = 'C:\\'
	-- config.default_prog = { 'C:\\Program Files\\PowerShell\\7\\pwsh.exe' }
	config.default_domain = "WSL:Ubuntu"
elseif wezterm.target_triple == "x86_64-unknown-linux-gnu" then
	config.default_prog = { "/bin/fish" }
end

config.background = {
	{
		source = {
			File = "/home/yorunai/Pictures/Wallpaper/miku_lying_bra.png",
		},
		opacity = 1,
		height = "Cover",
		width = "Cover",
	},
	{
		source = {
			Color = "black",
		},
		opacity = 0.7,
		height = "100%",
		width = "100%",
	},
}

config.hide_tab_bar_if_only_one_tab = true

local act = wezterm.action
config.disable_default_key_bindings = true
config.key_map_preference = "Mapped"
config.keys = {
	{ key = "9", mods = "CTRL|ALT", action = act.ActivateTabRelative(-1) },
	{ key = "0", mods = "CTRL|ALT", action = act.ActivateTabRelative(1) },
	{ key = "p", mods = "CTRL|ALT", action = act.ActivateCommandPalette },
	{ key = "t", mods = "CTRL|ALT", action = act.SpawnTab("CurrentPaneDomain") },
	{ key = "w", mods = "CTRL|ALT", action = act.CloseCurrentTab({ confirm = true }) },
	{ key = "u", mods = "CTRL|ALT", action = act.SplitHorizontal({ domain = "CurrentPaneDomain" }) },
	{ key = "i", mods = "CTRL|ALT", action = act.SplitVertical({ domain = "CurrentPaneDomain" }) },
	{ key = "ä", mods = "CTRL|ALT", action = act.CloseCurrentPane({ confirm = true }) },
	{ key = "h", mods = "CTRL|ALT", action = act.ActivatePaneDirection("Left") },
	{ key = "k", mods = "CTRL|ALT", action = act.ActivatePaneDirection("Up") },
	{ key = "j", mods = "CTRL|ALT", action = act.ActivatePaneDirection("Down") },
	{ key = "l", mods = "CTRL|ALT", action = act.ActivatePaneDirection("Right") },
	{ key = "v", mods = "CTRL", action = act.PasteFrom("Clipboard") },
	{ key = "V", mods = "CTRL", action = act.PasteFrom("Clipboard") },
}

for i = 1, 8 do
	-- CTRL+ALT + number to activate that tab
	table.insert(config.keys, {
		key = tostring(i),
		mods = "CTRL|ALT",
		action = act.ActivateTab(i - 1),
	})
end

wezterm.on("gui-startup", function(cmd)
	local tab, pane, window = mux.spawn_window(cmd or {})
	window:gui_window():maximize()
end)

return config
