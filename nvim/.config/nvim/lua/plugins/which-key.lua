return {
  'folke/which-key.nvim',
  event = 'VimEnter',
  opts = {
    spec = {
      { '<leader>c', group = '[C]ode', mode = { 'n', 'x' } },
      { '<leader>d', group = '[D]ocument' },
      { '<leader>r', group = '[R]ename' },
      { '<leader>s', group = '[S]earch' },
      { '<leader>w', group = '[W]orkspace' },
      { '<leader>t', group = '[T]oggle' },
      { '<leader>o', group = '[O]bsidian' },
      { '<leader>a', group = '[A]vante' },
      { '<leader>h', group = '[H]arpoon' },
    },
  },
}
