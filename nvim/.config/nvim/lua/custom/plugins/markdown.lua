return {
  {
    'MeanderingProgrammer/render-markdown.nvim',
    dependencies = { 'nvim-treesitter/nvim-treesitter', 'echasnovski/mini.nvim' }, -- if you use the mini.nvim suite
    -- dependencies = { 'nvim-treesitter/nvim-treesitter', 'echasnovski/mini.icons' }, -- if you use standalone mini plugins
    -- dependencies = { 'nvim-treesitter/nvim-treesitter', 'nvim-tree/nvim-web-devicons' }, -- if you prefer nvim-web-devicons
    ---@module 'render-markdown'
    ---@type render.md.UserConfig
    opts = {},
    config = function()
      require('render-markdown').setup {
        latex = { enabled = false },
        custom_handlers = {
          markdown = {
            extends = true,
            parse = function(root, buf)
              local marks = {}
              ---@param row integer
              ---@param start_col integer
              ---@param end_col integer
              ---@param conceal? string
              ---@param hl_group? string
              local function append(row, start_col, end_col, conceal, hl_group)
                table.insert(marks, {
                  conceal = true,
                  start_row = row,
                  start_col = start_col,
                  opts = { end_row = row, end_col = end_col, conceal = conceal, hl_group = hl_group },
                })
              end

              local start_row = root:range()
              local text = vim.treesitter.get_node_text(root, buf)
              for i, line in ipairs(vim.split(text, '\n', { plain = true })) do
                local row = start_row + i - 1
                ---@type integer|nil
                local position = 1
                while position ~= nil do
                  local start_col, end_col = line:find('(=)=[^=]+=(=)', position)
                  if start_col ~= nil and end_col ~= nil then
                    -- Translate 1 based index to 0 based index, update position
                    start_col, position = start_col - 1, end_col + 1
                    -- Hide first 2 equal signs
                    append(row, start_col, start_col + 2, '', nil)
                    -- Highlight contents
                    append(row, start_col, end_col, nil, 'DiffDelete')
                    -- Hide last 2 equal signs
                    append(row, end_col - 2, end_col, '', nil)
                  else
                    position = nil
                  end
                end
              end
              return marks
            end,
          },
        },
      }
    end,
  },
  {
    'epwalsh/obsidian.nvim',
    version = '*', -- recommended, use latest release instead of latest commit
    lazy = true,
    ft = 'markdown',
    -- Replace the above line with this if you only want to load obsidian.nvim for markdown files in your vault:
    -- event = {
    --   -- If you want to use the home shortcut '~' here you need to call 'vim.fn.expand'.
    --   -- E.g. "BufReadPre " .. vim.fn.expand "~" .. "/my-vault/*.md"
    --   -- refer to `:h file-pattern` for more examples
    --   "BufReadPre path/to/my-vault/*.md",
    --   "BufNewFile path/to/my-vault/*.md",
    -- },
    dependencies = {
      'nvim-lua/plenary.nvim',
      'hrsh7th/nvim-cmp',
      'nvim-telescope/telescope.nvim',
      'nvim-treesitter/nvim-treesitter',
    },
    opts = {
      dir = '~/SecondBrain/Second Brain/',
      ui = { enable = false },
    },
  },
}
