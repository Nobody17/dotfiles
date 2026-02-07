return {
  {
    'NickvanDyke/opencode.nvim',
    dependencies = {
      -- Recommended for `ask()` and `select()`.
      -- Required for `snacks` provider.
      ---@module 'snacks' <- Loads `snacks.nvim` types for configuration intellisense.
      { 'folke/snacks.nvim', opts = { input = {}, picker = {}, terminal = {} } },
    },
    config = function()
      ---@type opencode.Opts
      vim.g.opencode_opts = {
        -- Your configuration, if any — see `lua/opencode/config.lua`, or "goto definition" on the type or field.
      }

      -- Required for `opts.events.reload`.
      vim.o.autoread = true

      local wk = require 'which-key'
      wk.add {
        { '<leader>a', group = 'opencode' },
        { '<leader>as', group = 'session' },
        { '<leader>au', group = 'nav-up' },
        { '<leader>ad', group = 'nav-down' },
        { '<leader>ap', group = 'prompt' },
      }
      -- 2. Core Functions
      vim.keymap.set({ 'n', 'x' }, '<leader>aa', function()
        require('opencode').ask('@this: ', { submit = true })
      end, { desc = 'Ask' })

      vim.keymap.set({ 'n', 'x' }, '<leader>ax', function()
        require('opencode').select()
      end, { desc = 'Execute Action' })

      vim.keymap.set({ 'n', 't' }, '<leader>at', function()
        require('opencode').toggle()
      end, { desc = 'Toggle TUI' })

      -- 3. Session Group (<leader>as...)
      vim.keymap.set('n', '<leader>asl', function()
        require('opencode').command 'session.list'
      end, { desc = 'List' })
      vim.keymap.set('n', '<leader>asn', function()
        require('opencode').command 'session.new'
      end, { desc = 'New' })
      vim.keymap.set('n', '<leader>ass', function()
        require('opencode').command 'session.select'
      end, { desc = 'Select' })
      vim.keymap.set('n', '<leader>ash', function()
        require('opencode').command 'session.share'
      end, { desc = 'Share' })
      vim.keymap.set('n', '<leader>asi', function()
        require('opencode').command 'session.interrupt'
      end, { desc = 'Interrupt' })
      vim.keymap.set('n', '<leader>asc', function()
        require('opencode').command 'session.compact'
      end, { desc = 'Compact' })
      vim.keymap.set('n', '<leader>asz', function()
        require('opencode').command 'session.undo'
      end, { desc = 'Undo' })
      vim.keymap.set('n', '<leader>asr', function()
        require('opencode').command 'session.redo'
      end, { desc = 'Redo' })

      -- 4. Navigation Groups (<leader>au... and <leader>ad...)
      vim.keymap.set('n', '<leader>auk', function()
        require('opencode').command 'session.page.up'
      end, { desc = 'Page Up' })
      vim.keymap.set('n', '<leader>auu', function()
        require('opencode').command 'session.half.page.up'
      end, { desc = 'Half Page Up' })
      vim.keymap.set('n', '<leader>adj', function()
        require('opencode').command 'session.page.down'
      end, { desc = 'Page Down' })
      vim.keymap.set('n', '<leader>add', function()
        require('opencode').command 'session.half.page.down'
      end, { desc = 'Half Page Down' })
      vim.keymap.set('n', '<leader>ag', function()
        require('opencode').command 'session.first'
      end, { desc = 'Jump to First' })
      vim.keymap.set('n', '<leader>aG', function()
        require('opencode').command 'session.last'
      end, { desc = 'Jump to Last' })

      -- 5. Prompt & Agent (<leader>ap...)
      vim.keymap.set('n', '<leader>aps', function()
        require('opencode').command 'prompt.submit'
      end, { desc = 'Submit' })
      vim.keymap.set('n', '<leader>apc', function()
        require('opencode').command 'prompt.clear'
      end, { desc = 'Clear' })
      vim.keymap.set('n', '<leader>ay', function()
        require('opencode').command 'agent.cycle'
      end, { desc = 'Cycle Agent' })

      -- You may want these if you stick with the opinionated "<C-a>" and "<C-x>" above — otherwise consider "<leader>o…".
      -- vim.keymap.set('n', '+', '<C-a>', { desc = 'Increment under cursor', noremap = true })
      -- vim.keymap.set('n', '-', '<C-x>', { desc = 'Decrement under cursor', noremap = true })
    end,
  },
  {
    -- 'yetone/avante.nvim',
    -- event = 'VeryLazy',
    -- lazy = false,
    -- version = false, -- Set this to "*" to always pull the latest release version, or set it to false to update to the latest code changes.
    -- opts = {
    --   -- add any opts here
    -- },
    -- -- if you want to build from source then do `make BUILD_FROM_SOURCE=true`
    -- build = 'make',
    -- -- build = "powershell -ExecutionPolicy Bypass -File Build.ps1 -BuildFromSource false" -- for windows
    -- dependencies = {
    --   'stevearc/dressing.nvim',
    --   'nvim-lua/plenary.nvim',
    --   'MunifTanjim/nui.nvim',
    --   --- The below dependencies are optional,
    --   'hrsh7th/nvim-cmp', -- autocompletion for avante commands and mentions
    --   -- 'nvim-tree/nvim-web-devicons', -- or
    --   'echasnovski/mini.nvim',
    --   'zbirenbaum/copilot.lua', -- for providers='copilot'
    --   {
    --     -- support for image pasting
    --     'HakonHarnes/img-clip.nvim',
    --     event = 'VeryLazy',
    --     opts = {
    --       -- recommended settings
    --       default = {
    --         embed_image_as_base64 = false,
    --         prompt_for_file_name = false,
    --         drag_and_drop = {
    --           insert_mode = true,
    --         },
    --         -- required for Windows users
    --         use_absolute_path = true,
    --       },
    --     },
    --   },
    --   {
    --     -- Make sure to set this up properly if you have lazy=true
    --     'MeanderingProgrammer/render-markdown.nvim',
    --     opts = {
    --       file_types = { 'markdown', 'Avante' },
    --     },
    --     ft = { 'markdown', 'Avante' },
    --   },
    -- },
  },
  {
    -- 'supermaven-inc/supermaven-nvim',
    -- config = function()
    --   require('supermaven-nvim').setup {
    --     keymaps = {
    --       accept_suggestion = '<C-u>',
    --       clear_suggestion = '<C-i>',
    --       accept_word = '<C-o>',
    --     },
    --     -- color = {
    --     --   suggestion_color = '#ffffff',
    --     --   cterm = 244,
    --     -- },
    --     -- log_level = 'info', -- set to "off" to disable logging completely
    --     -- disable_inline_completion = false, -- disables inline completion for use with cmp
    --     -- disable_keymaps = false, -- disables built in keymaps for more manual control
    --     condition = function()
    --       return false
    --     end, -- condition to check for stopping supermaven, `true` means to stop supermaven when the condition is true.
    --   }
    -- end,
  },
}
