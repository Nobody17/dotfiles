"""Shared steps of dispatch-worker.py, start-integration.py and finish-integration.py.

The repository-specific commands come from the ledger:
  commands.worktree_create   shell command, run in ledger.repository; {branch}, {base}, {path} are replaced
  commands.worktree_facts    optional {ticket key: regular expression with one group}, applied to the output of
                             worktree_create; each match is stored in the ticket entry (for example the app URL)
  commands.worktree_start    optional shell command, run in the new worktree (for example its runtime stack)
  commands.worktree_remove   shell command, run in ledger.repository; {path} is replaced
  config.branch_pattern, config.worktree_pattern, config.candidate_branch_pattern   with {ticket}
  config.recovery_prefix, config.permission_mode, config.herdr_workspace, config.model, config.model_marker
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REFERENCES = SCRIPTS.parent / 'references'
UNFINISHED_OPERATION_FILES = ('rebase-merge', 'rebase-apply', 'MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD')
PROCESS_EXIT_WAIT_SECONDS = 10


class StepRefused(Exception):
    pass


def read_ledger(ledger_path):
    return json.loads(Path(ledger_path).read_text())


def write_ledger(ledger_path, ledger):
    ledger_path = Path(ledger_path)
    temporary = ledger_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(ledger_path)


def update_ledger(ledger_path, change):
    """Read the ledger, apply change(ledger), write it. Other scripts write the ledger too, so never keep a copy."""
    ledger = read_ledger(ledger_path)
    change(ledger)
    write_ledger(ledger_path, ledger)
    return ledger


def git(repository, *arguments, check=True):
    result = subprocess.run(['git', '-C', str(repository), *arguments], capture_output=True, text=True)
    if check and result.returncode:
        raise StepRefused(f'git {" ".join(arguments)} in {repository}: {result.stderr.strip()}')
    return result.stdout.strip()


def fill(template, **values):
    """Replace {name} for the given names only, so braces of the shell command itself stay."""
    for name, value in values.items():
        template = template.replace('{' + name + '}', str(value))
    return template


def run_shell(command, directory, purpose):
    result = subprocess.run(command, shell=True, cwd=directory, capture_output=True, text=True)
    if result.returncode:
        raise StepRefused(f'{purpose} failed (exit {result.returncode}): {command}\n{result.stdout}{result.stderr}')
    return result.stdout + result.stderr


def herdr(*arguments, check=True):
    result = subprocess.run(['herdr', *arguments], capture_output=True, text=True)
    if check and result.returncode:
        raise StepRefused(f'herdr {" ".join(arguments[:2])} failed: {result.stdout}{result.stderr}')
    return result.stdout


def ticket_names(ledger, ticket_id):
    config = ledger['config']
    return {
        'branch': fill(config['branch_pattern'], ticket=ticket_id),
        'worktree': fill(config['worktree_pattern'], ticket=ticket_id),
        'candidate_branch': fill(config['candidate_branch_pattern'], ticket=ticket_id),
    }


def worktree_is_clean(worktree):
    return git(worktree, 'status', '--porcelain') == ''


def unfinished_operations(worktree):
    git_directory = Path(git(worktree, 'rev-parse', '--absolute-git-dir'))
    return [name for name in UNFINISHED_OPERATION_FILES if (git_directory / name).exists()]


def captured_facts(patterns, output):
    facts = {}
    for key, pattern in (patterns or {}).items():
        match = re.search(pattern, output)
        if match:
            facts[key] = match.group(1)
    return facts


def render_assignment(ledger_path, template, output, ticket_id, values):
    command = [sys.executable, str(SCRIPTS / 'render-assignment.py'), str(template), str(output),
               '--ledger', str(ledger_path), '--ticket', ticket_id]
    for key, value in values.items():
        command += ['--set', f'{key}={value}']
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise StepRefused(f'cannot render {output}: {result.stderr.strip()}')


def start_session(ledger_path, *, name, role, directory, role_instructions, assignment, closing_sentence):
    """Launch a delegated Claude Code session, check its model, and send the bootstrap prompt."""
    config = read_ledger(ledger_path)['config']
    command = [sys.executable, str(SCRIPTS / 'launch-agent.py'), '--ledger', str(ledger_path),
               '--workspace', config['herdr_workspace'], '--cwd', str(directory), '--name', name, '--role', role,
               '--permission-mode', config['permission_mode']]
    if config.get('model'):
        command += ['--model', config['model']]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise StepRefused(f'launch of {name} failed: {result.stdout}{result.stderr}')
    marker = config.get('model_marker')
    if marker and marker not in herdr('agent', 'read', name, '--source', 'visible', '--lines', '40'):
        raise StepRefused(f'{name} does not show the model marker {marker!r}; report the substitution to the user '
                          f'before you assign work. The session runs and has no assignment.')
    herdr('agent', 'prompt', name,
          f'You work in an orchestrated run. Read your role instructions {role_instructions} and your assignment '
          f'{assignment}, then follow them. {closing_sentence}')


def close_sessions(ledger_path, roles, extra_tabs=()):
    """Close the Herdr tabs of the sessions with one of the roles, and extra tabs such as reviewers."""
    closed = []

    def change(ledger):
        for session in ledger.get('resources', {}).get('sessions', []):
            if session.get('role') in roles and session.get('status') != 'closed':
                herdr('tab', 'close', session['tab_id'], check=False)
                session['status'] = 'closed'
                closed.append(session['name'])
    update_ledger(ledger_path, change)
    for tab in extra_tabs:
        herdr('tab', 'close', tab, check=False)
        closed.append(tab)
    return closed


def processes_using(path):
    result = subprocess.run(['pgrep', '-fl', str(path)], capture_output=True, text=True)
    own = Path(sys.argv[0]).name
    return [line for line in result.stdout.splitlines() if own not in line and 'pgrep' not in line]


def wait_for_no_process(path, wait_seconds=PROCESS_EXIT_WAIT_SECONDS):
    give_up_at = time.time() + wait_seconds
    while True:
        processes = processes_using(path)
        if not processes or time.time() >= give_up_at:
            return processes
        time.sleep(1)


def fail(error):
    print(f'refused: {error}', file=sys.stderr)
    return 1
