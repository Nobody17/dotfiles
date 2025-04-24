return {
  { -- Autoformat
    'stevearc/conform.nvim',
    event = { 'BufWritePre' },
    cmd = { 'ConformInfo' },
    keys = {
      {
        '<leader>f',
        function()
          require('conform').format { async = true, lsp_format = 'fallback' }
        end,
        mode = '',
        desc = '[F]ormat buffer',
      },
    },
    opts = {
      notify_on_error = false,
      format_on_save = function(bufnr)
        -- Disable "format_on_save lsp_fallback" for languages that don't
        -- have a well standardized coding style. You can add additional
        -- languages here or re-enable it for the disabled ones.
        local disable_filetypes = { c = false, cpp = false }
        local lsp_format_opt
        if disable_filetypes[vim.bo[bufnr].filetype] then
          lsp_format_opt = 'never'
        else
          lsp_format_opt = 'fallback'
        end
        return {
          timeout_ms = 500,
          lsp_format = lsp_format_opt,
        }
      end,
      formatters_by_ft = {
        lua = { 'stylua' },
        -- Conform can also run multiple formatters sequentially
        python = {
          -- To fix auto-fixable lint errors.
          'ruff_fix',
          -- To run the Ruff formatter.
          'ruff_format',
          -- To organize the imports.
          'ruff_organize_imports',
        },
        markdown = {
          'prettier',
          'deno_fmt',
          'mdformat',
          stop_after_first = true,
        },
        sql = {
          'sqlfmt',
          -- The following is very slow, timeout_ms needs to be higher when used:
          -- 'sqlfluff',
        },
        -- You can use 'stop_after_first' to run the first available formatter from the list
        javascript = { 'prettier', 'deno_fmt', stop_after_first = true },
        typescript = { 'prettier', 'deno_fmt', stop_after_first = true },
        json = { 'prettier', 'deno_fmt', stop_after_first = true },
        vue = { 'prettier' },
        html = { 'prettier' },
        css = { 'prettier' },
        php = { 'pint' },
      },
    },
  },
  -- {
  --   'nmac427/guess-indent.nvim',
  --   opts = {},
  -- },
}
