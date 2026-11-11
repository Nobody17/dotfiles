-- Super+h/j/k/l moves the focus between Neovim windows, Herdr panes,
-- macOS windows and monitors, in this order.
--
-- AeroSpace takes Super+h/j/k/l before any terminal sees it, so Neovim never
-- gets the key. Instead, ~/.config/aerospace/focus-pane-or-window.sh asks
-- Neovim over a socket: it calls focus_neighbor(direction) and reads the
-- answer. 1 means that Neovim moved the focus. 0 means that there is no
-- window in that direction, so the script moves to the next Herdr pane.
--
-- The script finds the socket by the PIDs that Herdr reports as foreground
-- processes of the pane. That is the PID of the Neovim TUI. The Neovim
-- server is a child of the TUI (started with --embed), so the socket name
-- uses the parent PID in that case.

local herdr_navigation = {}

local socket_directory = vim.fn.stdpath 'state' .. '/herdr-navigation'

local window_command_of_direction = {
  left = 'h',
  down = 'j',
  up = 'k',
  right = 'l',
}

local function is_embedded_server(arguments)
  return vim.tbl_contains(arguments, '--embed')
end

local function socket_path_for(process_id)
  return socket_directory .. '/' .. process_id .. '.sock'
end

-- Returns 1 when a window exists in that direction (the focus moves to it),
-- otherwise 0. The window change runs scheduled, outside the RPC request.
function herdr_navigation.focus_neighbor(direction)
  local window_command = window_command_of_direction[direction]
  if window_command == nil then
    return 0
  end

  local neighbor_window_number = vim.fn.winnr(window_command)
  if neighbor_window_number == vim.fn.winnr() then
    return 0
  end

  local neighbor_window_id = vim.fn.win_getid(neighbor_window_number)
  vim.schedule(function()
    if vim.api.nvim_win_is_valid(neighbor_window_id) then
      vim.api.nvim_set_current_win(neighbor_window_id)
    end
  end)
  return 1
end

local function process_is_running(process_id)
  return vim.uv.kill(process_id, 0) == 0
end

-- Neovim does not always remove its socket, for example when Herdr closes
-- the pane. Remove the sockets whose process is gone.
local function remove_dead_sockets()
  for file_name in vim.fs.dir(socket_directory) do
    local process_id = tonumber(file_name:match '^(%d+)%.sock$')
    if process_id ~= nil and not process_is_running(process_id) then
      os.remove(socket_directory .. '/' .. file_name)
    end
  end
end

function herdr_navigation.setup()
  if vim.env.HERDR_PANE_ID == nil then
    return
  end

  local terminal_process_id = is_embedded_server(vim.v.argv) and vim.uv.os_getppid() or vim.fn.getpid()
  local socket_path = socket_path_for(terminal_process_id)

  vim.fn.mkdir(socket_directory, 'p')
  remove_dead_sockets()
  -- A file with this name belongs to a dead process with the same PID.
  os.remove(socket_path)
  local started = pcall(vim.fn.serverstart, socket_path)
  if not started then
    return
  end

  vim.api.nvim_create_autocmd('VimLeavePre', {
    group = vim.api.nvim_create_augroup('herdr-navigation', { clear = true }),
    callback = function()
      pcall(vim.fn.serverstop, socket_path)
      os.remove(socket_path)
    end,
  })
end

return herdr_navigation
