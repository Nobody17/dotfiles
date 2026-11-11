-- Step from a single-commit diffview (`:DiffviewOpen <hash>^!`) to the next
-- newer or the next older commit, without a commit list.
--
-- Newer means: the next commit on the way from the shown commit to HEAD.
-- Older means: the first parent of the shown commit.
-- The selected file and the path filter stay the same.

local diffview_commit_step = {}

local function run_git(repository_path, arguments)
  local command = vim.list_extend({ 'git', '-C', repository_path }, arguments)
  local result = vim.system(command, { text = true }):wait()
  if result.code ~= 0 then
    return nil
  end
  return vim.trim(result.stdout)
end

local function first_line(text)
  if text == nil or text == '' then
    return nil
  end
  return text:match '^[^\n]+'
end

local function newer_commit(repository_path, commit)
  local commits_to_head = run_git(repository_path, {
    'rev-list', '--topo-order', '--reverse', '--ancestry-path', commit .. '..HEAD',
  })
  return first_line(commits_to_head)
end

local function older_commit(repository_path, commit)
  return first_line(run_git(repository_path, { 'rev-parse', '--verify', '--quiet', commit .. '^' }))
end

local find_neighbor_commit = {
  newer = newer_commit,
  older = older_commit,
}

local message_at_end = {
  newer = 'Kein neuerer Commit bis HEAD',
  older = 'Kein älterer Commit',
}

local function open_command(commit, selected_path, path_arguments)
  local parts = { 'DiffviewOpen', commit .. '^!' }
  if selected_path ~= nil then
    table.insert(parts, '--selected-file=' .. vim.fn.fnameescape(selected_path))
  end
  if path_arguments ~= nil and #path_arguments > 0 then
    table.insert(parts, '--')
    for _, path_argument in ipairs(path_arguments) do
      table.insert(parts, vim.fn.fnameescape(path_argument))
    end
  end
  return table.concat(parts, ' ')
end

-- direction: 'newer' or 'older'
function diffview_commit_step.open_neighbor(direction)
  local view = require('diffview.lib').get_current_view()
  local shown_commit = view and view.right and view.right.commit
  if shown_commit == nil then
    vim.notify('Nur in einer Diffview mit einem Commit', vim.log.levels.WARN)
    return
  end

  local repository_path = view.adapter.ctx.toplevel
  local neighbor_commit = find_neighbor_commit[direction](repository_path, shown_commit)
  if neighbor_commit == nil then
    vim.notify(message_at_end[direction], vim.log.levels.INFO)
    return
  end

  local current_file = view:infer_cur_file()
  local selected_path = current_file and (repository_path .. '/' .. current_file.path)
  local command = open_command(neighbor_commit, selected_path, view.path_args)

  vim.cmd 'DiffviewClose'
  vim.cmd(command)
end

return diffview_commit_step
