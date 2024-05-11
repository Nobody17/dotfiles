
-- Pull in the wezterm API
local wezterm = require 'wezterm'

-- This will hold the configuration.
local config = wezterm.config_builder()

-- This is where you actually apply your config choices

-- For example, changing the color scheme:
config.color_scheme = 'Ayu Mirage'

config.default_cwd = 'C:\\'
config.default_prog = {'C:\\Program Files\\PowerShell\\7\\pwsh.exe'}

-- and finally, return the configuration to wezterm

return config
