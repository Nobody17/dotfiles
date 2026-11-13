-- Clear highlights on search when pressing <Esc> in normal mode
--  See `:help hlsearch`
vim.keymap.set('n', '<esc>', '<cmd>nohlsearch<cr>')

-- Diagnostic keymaps
vim.keymap.set('n', '<leader>q', vim.diagnostic.setloclist, { desc = 'Open diagnostic [Q]uickfix list' })

-- Exit terminal mode in the builtin terminal with a shortcut that is a bit easier
-- for people to discover. Otherwise, you normally need to press <C-\><C-n>, which
-- is not what someone will guess without a bit more experience.
--
-- NOTE: This won't work in all terminal emulators/tmux/etc. Try your own mapping
-- or just use <C-\><C-n> to exit terminal mode
vim.keymap.set('t', '<Esc><Esc>', '<C-\\><C-n>', { desc = 'Exit terminal mode' })

-- TIP: Disable arrow keys in normal mode
vim.keymap.set('n', '<left>', '<cmd>echo "Use h to move!!"<CR>')
vim.keymap.set('n', '<right>', '<cmd>echo "Use l to move!!"<CR>')
vim.keymap.set('n', '<up>', '<cmd>echo "Use k to move!!"<CR>')
vim.keymap.set('n', '<down>', '<cmd>echo "Use j to move!!"<CR>')

-- Super+h/j/k/l moves between windows, see lua/herdr-navigation.lua

-- In visual mode, move selected lines up and down (with automatic indentation)
vim.keymap.set('v', 'J', ":m '>+1<CR>gv=gv")
vim.keymap.set('v', 'K', ":m '<-2<CR>gv=gv")

-- Keep cursor centered on the screen when searching or moving half pages
vim.keymap.set('n', '<C-d>', '<C-d>zz')
vim.keymap.set('n', '<C-u>', '<C-u>zz')

vim.keymap.set('n', '<n>', 'nzzzv')
vim.keymap.set('n', '<N>', 'Nzzzv')

vim.keymap.set('x', '<leader>p', '"_dP', { desc = '[P]aste without overwriting paste register' })

vim.keymap.set('n', '<leader>y', '"+y', { desc = '[Y]ank into system clipboard' })
vim.keymap.set('v', '<leader>y', '"+y', { desc = '[Y]ank into system clipboard' })
vim.keymap.set('n', '<leader>Y', '"+y$', { desc = '[Y]ank to end of line into system clipboard' })

vim.keymap.set('n', '<leader>d', '"_d', { desc = '[D]elete into void register' })
vim.keymap.set('v', '<leader>d', '"_d', { desc = '[D]elete into void register' })
