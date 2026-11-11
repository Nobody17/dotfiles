local function open_neighbor_commit(direction)
  return function()
    require('diffview-commit-step').open_neighbor(direction)
  end
end

local commit_step_keymaps = {
  { 'n', ']C', open_neighbor_commit 'newer', { desc = 'Nächst neuerer Commit' } },
  { 'n', '[C', open_neighbor_commit 'older', { desc = 'Nächst älterer Commit' } },
}

return {
  {
    'sindrets/diffview.nvim',
    opts = {
      keymaps = {
        view = commit_step_keymaps,
        file_panel = commit_step_keymaps,
      },
    },
  },
  {
    'lewis6991/gitsigns.nvim',
    opts = {
      signs = {
        add = { text = '+' },
        change = { text = '~' },
        delete = { text = '_' },
        topdelete = { text = '‾' },
        changedelete = { text = '~' },
      },
    },
  },
}
