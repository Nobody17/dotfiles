-- Pull in the wezterm API
local wezterm = require 'wezterm'
local mux = wezterm.mux

-- This will hold the configuration.
local config = wezterm.config_builder()

-- This is where you actually apply your config choices

-- For example, changing the color scheme:
config.color_scheme = 'Catppuccin Mocha'

config.default_cwd = 'C:\\'
config.default_prog = { 'C:\\Program Files\\PowerShell\\7\\pwsh.exe' }

local act = wezterm.action
config.disable_default_key_bindings = true
config.key_map_preference = "Mapped"
config.keys = {
  { key = '9', mods = 'CTRL|ALT', action = act.ActivateTabRelative(-1) },
  { key = '0', mods = 'CTRL|ALT', action = act.ActivateTabRelative(1) },
  { key = 'p', mods = 'CTRL|ALT', action = act.ActivateCommandPalette },
  { key = 't', mods = 'CTRL|ALT', action = act.SpawnTab 'CurrentPaneDomain' },
  { key = 'w', mods = 'CTRL|ALT', action = act.CloseCurrentTab { confirm = true } },
  { key = 'h', mods = 'CTRL|ALT', action = act.SplitHorizontal { domain = 'CurrentPaneDomain' } },
  { key = 'j', mods = 'CTRL|ALT', action = act.SplitVertical { domain = 'CurrentPaneDomain' } },
  { key = 'ä', mods = 'CTRL|ALT', action = act.CloseCurrentPane { confirm = true } },
  { key = 'a', mods = 'CTRL|ALT', action = act.ActivatePaneDirection 'Left' },
  { key = 's', mods = 'CTRL|ALT', action = act.ActivatePaneDirection 'Up' },
  { key = 'd', mods = 'CTRL|ALT', action = act.ActivatePaneDirection 'Down' },
  { key = 'f', mods = 'CTRL|ALT', action = act.ActivatePaneDirection 'Right' },
}

for i = 1, 8 do
  -- CTRL+ALT + number to activate that tab
  table.insert(config.keys, {
    key = tostring(i),
    mods = 'CTRL|ALT',
    action = act.ActivateTab(i - 1),
  })
end

wezterm.on("gui-startup", function(cmd)
  local tab, pane, window = mux.spawn_window(cmd or {})
  window:gui_window():maximize()
end)

return config
