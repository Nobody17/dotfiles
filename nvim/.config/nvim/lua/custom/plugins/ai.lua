return {
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
    'supermaven-inc/supermaven-nvim',
    config = function()
      require('supermaven-nvim').setup {
        keymaps = {
          accept_suggestion = '<C-u>',
          clear_suggestion = '<C-i>',
          accept_word = '<C-o>',
        },
        -- color = {
        --   suggestion_color = '#ffffff',
        --   cterm = 244,
        -- },
        -- log_level = 'info', -- set to "off" to disable logging completely
        -- disable_inline_completion = false, -- disables inline completion for use with cmp
        -- disable_keymaps = false, -- disables built in keymaps for more manual control
        condition = function()
          return false
        end, -- condition to check for stopping supermaven, `true` means to stop supermaven when the condition is true.
      }
    end,
  },
}
