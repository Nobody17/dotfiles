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
    keys = {
      vim.keymap.set('n', '<leader>on', '<cmd>ObsidianNew<cr>', { desc = '[O]bsidian: Open [N]ew File' }),
      vim.keymap.set(
        'n',
        '<leader>oh',
        '<cmd>ObsidianFollowLink hsplit<cr>',
        { desc = '[O]bsidian: Open File in [H]orizontal split' }
      ),
      vim.keymap.set(
        'n',
        '<leader>ov',
        '<cmd>ObsidianFollowLink vsplit<cr>',
        { desc = '[O]bsidian: Open File in [V]ertical split' }
      ),
      vim.keymap.set(
        'n',
        '<leader>ob',
        '<cmd>ObsidianBacklinks<cr>',
        { desc = '[O]bsidian: Open a picker with [B]acklinks' }
      ),
      vim.keymap.set('n', '<leader>os', '<cmd>ObsidianSearch<cr>', { desc = '[O]bsidian: Open a picker to [S]earch' }),
    },
    opts = {
      -- templates = {
      --   folder = '/templates',
      --   date_format = '%Y-%m-%d-%a',
      --   time_format = '%H:%M',
      -- },
      workspaces = {
        -- { name = 'oldvault', path = '~/SecondBrain/Second Brain/' },
        { name = 'secondbrain', path = '~/Documents/ObsidianVaults/SecondBrain/' },
      },
      callbacks = {
        -- Runs anytime you leave the buffer for a note.
        ---@param client obsidian.Client
        ---@param note obsidian.Note
        ---@diagnostic disable-next-line: unused-local
        leave_note = function(client, note)
          vim.api.nvim_buf_call(note.bufnr or 0, function()
            vim.cmd 'silent w'
          end)
        end,
      },
      ui = { enable = false },
      -- Optional, customize how note IDs are generated given an optional title.
      ---@param title string|?
      ---@return string
      note_id_func = function(title)
        -- Create note IDs in a Zettelkasten format with a timestamp and a suffix.
        -- In this case a note with the title 'My new note' will be given an ID that looks
        -- like '1657296016-my-new-note', and therefore the file name '1657296016-my-new-note.md'
        local suffix = ''
        if title ~= nil then
          -- If title is given, transform it into valid file name.
          suffix = title:gsub(' ', '-'):gsub('[^A-Za-z0-9-]', ''):lower()
        else
          -- If title is nil, just add 4 random uppercase letters to the suffix.
          for _ = 1, 4 do
            suffix = suffix .. string.char(math.random(65, 90))
          end
        end
        return tostring(os.time()) .. '-' .. suffix
      end,
      attachments = {
        img_folder = 'files/images/',
      },
    },
  },
}
