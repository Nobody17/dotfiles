return {
  'ThePrimeagen/harpoon',
  branch = 'harpoon2',
  dependencies = { 'nvim-lua/plenary.nvim', 'nvim-telescope/telescope.nvim' },
  config = function()
    local harpoon = require 'harpoon'
    harpoon:setup()
    local telescope_conf = require('telescope.config').values
    local function toggle_telescope(harpoon_files)
      local file_paths = {}
      for _, item in ipairs(harpoon_files.items) do
        table.insert(file_paths, item.value)
      end

      require('telescope.pickers')
        .new({}, {
          prompt_title = 'Harpoon',
          finder = require('telescope.finders').new_table {
            results = file_paths,
          },
          previewer = telescope_conf.file_previewer {},
          sorter = telescope_conf.generic_sorter {},
        })
        :find()
    end
    vim.keymap.set('n', '<leader>ha', function()
      harpoon:list():add()
    end, { desc = '[H]arpoon: [A]dd to list' })
    vim.keymap.set('n', '<leader>hr', function()
      harpoon:list():remove()
    end, { desc = '[H]arpoon: [R]emove from list' })
    vim.keymap.set('n', '<leader>ht', function()
      -- toggle_telescope(harpoon:list())
      harpoon.ui:toggle_quick_menu(harpoon:list())
    end, { desc = '[H]arpoon: [T]oggle list' })

    vim.keymap.set('n', '<A-h>', function()
      harpoon:list():select(1)
    end)
    vim.keymap.set('n', '<A-j>', function()
      harpoon:list():select(2)
    end)
    vim.keymap.set('n', '<A-k>', function()
      harpoon:list():select(3)
    end)
    vim.keymap.set('n', '<A-l>', function()
      harpoon:list():select(4)
    end)
    vim.keymap.set('n', '<A-p>', function()
      harpoon:list():select(5)
    end)
  end,
}
