return {
  {
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
  },
  {
    'https://codeberg.org/andyg/leap.nvim',
    config = function()
      vim.keymap.set({ 'n', 'x', 'o' }, 's', '<Plug>(leap)')
      vim.keymap.set('n', 'S', '<Plug>(leap-from-window)')

      vim.keymap.set({ 'x', 'o' }, 'an', function()
        require('leap.treesitter').select {
          opts = require('leap.user').with_traversal_keys('n', 'N'),
        }
      end)

      -- Highly recommended: define a preview filter to reduce visual noise
      -- and the blinking effect after the first keypress.
      -- For example, define word boundaries as the common case, that is, skip
      -- preview for matches starting with whitespace or an alphabetic
      -- mid-word character: foobar[baaz] = quux
      --                     *    ***  ** * *  *
      require('leap').opts.preview = function(ch0, ch1, ch2)
        return not (ch1:match '%s' or (ch0:match '%a' and ch1:match '%a' and ch2:match '%a'))
      end

      -- Enable the traversal keys to repeat the previous search without
      -- explicitly invoking Leap (`<cr><cr>...` instead of `s<cr><cr>...`):
      do
        local clever = require('leap.user').with_traversal_keys
        -- For relative directions, set the `backward` flags according to:
        -- local prev_backward = require('leap').state['repeat'].backward
        vim.keymap.set({ 'n', 'x', 'o' }, '<cr>', function()
          require('leap').leap {
            ['repeat'] = true,
            opts = clever('<cr>', '<bs>'),
          }
        end)
        vim.keymap.set({ 'n', 'x', 'o' }, '<bs>', function()
          require('leap').leap {
            ['repeat'] = true,
            opts = clever('<bs>', '<cr>'),
            backward = true,
          }
        end)
      end

      -- Set automatic paste after remote yank operations:
      vim.api.nvim_create_autocmd('User', {
        pattern = 'RemoteOperationDone',
        group = vim.api.nvim_create_augroup('LeapRemote', {}),
        callback = function(event)
          if vim.v.operator == 'y' and event.data.register == '"' then
            vim.cmd 'normal! p'
          end
        end,
      })
    end,
  },
}
