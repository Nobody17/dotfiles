# Code Context

## Files Retrieved
1. `init.lua` (lines 1-30) - leader setup, yank autocmd, lazy.nvim bootstrap/setup.
2. `plugin/settings.lua` (lines 1-65) - global/editor options.
3. `plugin/keymaps.lua` (lines 1-45) - global keymaps.
4. `lua/custom/plugins/lsp.lua` (lines 1-229) - lazydev, Mason, LSP servers, LspAttach maps/autocmds.
5. `lua/custom/plugins/autocompletion.lua` (lines 1-140) - nvim-cmp, LuaSnip, sources, autopairs.
6. `lua/custom/plugins/formatting.lua` (lines 1-71) - conform.nvim format-on-save and formatter map.
7. `lua/custom/plugins/lint.lua` (lines 1-61) - nvim-lint linters and lint autocmds.
8. `lua/custom/plugins/telescope.lua` (lines 1-83) - Telescope deps/extensions/keymaps.
9. `lua/custom/plugins/markdown.lua` (lines 1-146) - render-markdown and Obsidian setup.
10. `lua/custom/plugins/mini.lua` (lines 1-55) - mini.ai/surround/splitjoin/statusline/jump2d.
11. `lua/custom/plugins/movement.lua` (lines 1-110) - Harpoon and Leap config/keymaps.
12. `lua/custom/plugins/sql.lua` (lines 1-11) - dadbod plugins.
13. `lua/custom/plugins/which-key.lua` (lines 1-17) - which-key groups.
14. `lua/custom/plugins/autotag.lua` (lines 1-15) - nvim-ts-autotag.
15. `lua/custom/plugins/color.lua` (lines 1-14) - catppuccin.
16. `lua/custom/plugins/explorer.lua` (lines 1-11) - oil.nvim.
17. `lua/custom/plugins/git.lua` (lines 1-15), `research.lua` (lines 23-36), `undotree.lua` (lines 1-6), `ai.lua` (lines 1-71), `zellij-nav.lua` (lines 1-14) - smaller/plugin-disabled specs.
18. `lazy-lock.json` (lines 1-45) - locked plugin set.
19. `README.md` (line 1) - still Kickstart template.

## Key Code

### Structure / loading
- `init.lua` only sets leaders, yank highlight, bootstraps lazy, then imports all specs via `require('lazy').setup('custom/plugins', ...)` (`init.lua:1-30`).
- Settings and global keymaps live under `plugin/`, so they are auto-sourced as runtime plugin files, not explicitly required before lazy setup (`plugin/settings.lua:1-65`, `plugin/keymaps.lua:1-45`). This matters because plugin specs also read globals like `vim.g.have_nerd_font` (`plugin/settings.lua:1`, `lua/custom/plugins/telescope.lua:23`, `lua/custom/plugins/mini.lua:39`). Prefer moving settings/keymaps to `lua/custom/` and requiring them early from `init.lua`.
- Typo: lazy change detection uses `nofify = false` (`init.lua:27-29`); lazy.nvim expects `notify`, so notifications are probably not disabled.

### Active plugin list by area
- UI/navigation: catppuccin (`color.lua:1-14`), oil (`explorer.lua:1-11`), Telescope + fzf/ui-select/devicons (`telescope.lua:1-24`), which-key (`which-key.lua:1-17`), mini.nvim modules (`mini.lua:1-55`), Harpoon/Leap (`movement.lua:1-110`), undotree (`undotree.lua:1-6`).
- Git: diffview and gitsigns (`git.lua:1-15`).
- LSP/tooling: lazydev/luvit-meta, nvim-lspconfig, mason, mason-lspconfig, mason-tool-installer, fidget, cmp-nvim-lsp (`lsp.lua:1-28`).
- Completion/editing: nvim-cmp, LuaSnip, cmp sources, autopairs (`autocompletion.lua:1-140`), nvim-ts-autotag (`autotag.lua:1-15`).
- Formatting/lint: conform (`formatting.lua:1-71`), nvim-lint (`lint.lua:1-61`).
- Markdown/research/SQL: render-markdown, obsidian, vimtex, dadbod suite (`markdown.lua:1-146`, `research.lua:23-36`, `sql.lua:1-11`).
- System/learning/microcontroller: vim-suda, vim-be-good, esp32 (`system.lua:1-3`, `learning-vim.lua:1-3`, `microcontroller.lua:1-3`).
- Disabled/stale placeholders: AI specs contain only commented plugin declarations (`ai.lua:1-71`); zellij-nav returns only commented config (`zellij-nav.lua:1-14`); which-key still advertises Avante group (`which-key.lua:13`).

### LSP / completion / formatting / lint
- LSP servers configured: `marksman`, `pyright`, `eslint`, `ts_ls`, `texlab`, `lua_ls` (`lsp.lua:152-188`). Mason installs those plus `stylua`, `prettier`, `ruff`, `mdformat`, `sqlfluff`, `sqlfmt`, `texlab`, `elixirls` (`lsp.lua:200-211`).
- Modern Neovim LSP API is used: `vim.lsp.config(server_name, server)` with mason-lspconfig `automatic_enable = true` (`lsp.lua:213-220`). This is OK on the observed Neovim `v0.12.2`; it would not be compatible with older 0.10 configs.
- LspAttach maps Telescope LSP pickers and core LSP actions (`lsp.lua:40-88`), document highlighting (`lsp.lua:95-117`), and inlay hint toggle (`lsp.lua:123-126`).
- Completion uses nvim-cmp sources `lazydev`, `nvim_lsp`, `luasnip`, `path`, `buffer`, plus SQL dadbod completion (`autocompletion.lua:46-124`). Snippet jump mappings and friendly-snippets are commented out (`autocompletion.lua:23-28`, `92-101`).
- Conform formats on save and `<leader>f`; formatters include stylua, ruff, prettier/deno_fmt/mdformat, sqlfmt, pint (`formatting.lua:6-64`).
- nvim-lint runs sqlfluff, eslint, jsonlint on `BufEnter`, `BufWritePost`, `TextChanged`, and `InsertLeave` (`lint.lua:8-15`, `51-57`).

### Findings / improvement opportunities
- **Potential bug:** `disable_filetypes = { c = false, cpp = false }` never disables C/C++ despite the comment saying to disable them (`formatting.lua:18-28`). If intended, values should be truthy.
- **Potential clean-install issue:** nvim-cmp dependencies put both `'neovim/nvim-lspconfig'` and `'L3MON4D3/LuaSnip'` in one spec table (`autocompletion.lua:7-18`). Make LuaSnip its own dependency spec so the `build = 'make install_jsregexp'` clearly applies to LuaSnip, not lspconfig.
- **Missing managed tools:** lint/format config references `jsonlint`, `deno_fmt`/`deno`, and `pint` (`lint.lua:14`, `formatting.lua:47`, `57-59`, `63`) but Mason ensure list does not include `jsonlint`, `deno`, or `pint` (`lsp.lua:200-211`). `eslint` linting also assumes a project/system executable (`lint.lua:10-11`).
- **No Tree-sitter manager:** `render-markdown` uses `vim.treesitter.get_node_text` (`markdown.lua:31-32`) and nvim-ts-autotag is enabled (`autotag.lua:1-15`), but `nvim-treesitter/nvim-treesitter` is only commented (`markdown.lua:5`) and absent from `lazy-lock.json:1-45`. Parser availability may be inconsistent.
- **Obsidian lazy keys are wrong shape:** `keys = { vim.keymap.set(...) }` executes mappings immediately and stores nils instead of lazy key specs (`markdown.lua:78-99`). These mappings likely will not lazy-load Obsidian outside its vault events (`markdown.lua:66-72`).
- **Duplicate specs:** dadbod and dadbod-completion are top-level specs and also dependencies of dadbod-ui (`sql.lua:2-8`). Lazy can merge, but this is redundant.
- **Unused/no-op code:** LSP `opts` function just returns opts (`lsp.lua:29-34`); `mason_elixirls`, `asdf_init`, and `mason_registry` are assigned but unused (`lsp.lua:138-141`); `mini.surround` local is unused (`mini.lua:30`); Harpoon Telescope picker helper is defined but not used (`movement.lua:10-26`, `33-35`).
- **Keymap semantics/conflicts:** `<leader>d` is a delete-to-void action (`plugin/keymaps.lua:44-45`) while which-key labels `<leader>d` as `[D]ocument` (`which-key.lua:7`) and LSP uses `<leader>ds` for document symbols (`lsp.lua:72`); this works but causes prefix/action ambiguity. Zellij comments reserve `<C-h/j/k/l>` that already map to window movement (`plugin/keymaps.lua:22-25`, `zellij-nav.lua:7-10`).
- **Lint frequency risk:** linting on every `TextChanged` can be noisy/slow, especially with `sqlfluff` (`lint.lua:9`, `52`). Consider restricting heavy linters to save/insert-leave.
- **No DAP/test setup:** no active `nvim-dap`, `neotest`, or test runner config found; only a commented neotest dependency in Papis comments (`research.lua:8`).
- **Deprecated APIs:** no clear active deprecated API use found; config uses `vim.keymap.set`, `nvim_create_autocmd`, and modern `vim.lsp.config`. Only legacy alias fallback is `(vim.uv or vim.loop)` in lazy bootstrap (`init.lua:15`), which is harmless on current Neovim but can be simplified to `vim.uv` if dropping old versions.
- **Docs:** `README.md` is still the Kickstart template (`README.md:1`); update it to document this config's plugins, required external tools, and language support.

## Architecture
- Startup enters `init.lua`, bootstraps lazy.nvim, then imports every Lua module under `lua/custom/plugins` as lazy specs (`init.lua:12-30`).
- Editor options/keymaps are auto-sourced from `plugin/settings.lua` and `plugin/keymaps.lua` rather than required from `init.lua`.
- LSP setup installs/configures servers through Mason and Neovim's built-in LSP; completion capabilities come from nvim-cmp; formatting is delegated to conform; linting is delegated to nvim-lint.
- Telescope is the central picker used by global search mappings and LSP navigation mappings.

## Start Here
Open `init.lua` first: it controls lazy setup and contains the `nofify` typo/load-order issue. Then inspect `lua/custom/plugins/lsp.lua`, `formatting.lua`, and `lint.lua` for the highest-impact tooling fixes.