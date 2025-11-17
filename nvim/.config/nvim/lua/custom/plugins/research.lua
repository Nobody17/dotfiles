return {
  -- {
  --   'jghauser/papis.nvim',
  --   dependencies = {
  --     'kkharji/sqlite.lua',
  --     'MunifTanjim/nui.nvim',
  --     'pysan3/pathlib.nvim',
  --     'nvim-neotest/nvim-nio',
  --     -- if not already installed, you may also want:
  --     'hrsh7th/nvim-cmp',
  --
  --     -- Choose one of the following two if not already installed:
  --     'nvim-telescope/telescope.nvim',
  --     -- "folke/snacks.nvim",
  --   },
  --   config = function()
  --     require('papis').setup {
  --       enable_keymaps = true,
  --       init_filetypes = { 'markdown', 'norg', 'yaml', 'typst', 'tex' },
  --     }
  --   end,
  -- },
  {
    'lervag/vimtex',
    ft = { 'tex', 'plaintex', 'latex' }, -- lazy load by filetype
    init = function()
      vim.g.vimtex_view_method = 'zathura'
      vim.g.vimtex_compiler_method = 'latexmk'
      vim.g.vimtex_compiler_latexmk = {
        options = { '-pdf', '-interaction=nonstopmode', '-synctex=1', '-file-line-error' },
      }
      vim.g.vimtex_compiler_progname = 'nvr'
      -- vim.g.maplocalleader = ','
    end,
  },
}
