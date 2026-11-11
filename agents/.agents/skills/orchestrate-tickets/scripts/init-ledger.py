#!/usr/bin/env python3
"""Create the run directory and a starter ledger.json for an orchestrate-tickets run.

Usage: init-ledger.py --run <run-directory> --repository <main checkout> --spec <spec file>
                      --tickets <directory of ticket files> --base-branch <branch> --prefix <agent prefix>
                      --workspace <herdr workspace> [--review-after-minutes M] [--min-free-disk-gb N]

Writes <run>/ledger.json with the keys that the run scripts read (heavy_jobs, resource_watch,
resources, integration.lock, commands, the patterns in config) and one entry per ticket file, creates
handoffs/, messages/, assignments/templates/ and evidence/, and copies the starter templates of
references/templates/ for you to adapt to the repository. The base SHA comes from Git, and every value is written as JSON,
so no text replacement touches the ledger. Prints the keys that still need a value: fill them, then
check each ticket's depends_on against the ticket text. Refuses a run directory that has a ledger.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TICKET_NUMBER = re.compile(r'^(\d+)')
BLOCKED_BY_LINE = re.compile(r'blocked by', re.IGNORECASE)
RUN_FOLDERS = ('handoffs', 'messages', 'assignments/templates', 'evidence')
TO_FILL = 'TO FILL'
STARTER_TEMPLATES = Path(__file__).resolve().parents[1] / 'references/templates'


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--repository', required=True, type=Path)
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--tickets', required=True, type=Path)
    parser.add_argument('--base-branch', required=True)
    parser.add_argument('--prefix', required=True, help='agent name prefix, for example nb-')
    parser.add_argument('--workspace', required=True, help='Herdr workspace ID for the run sessions')
    parser.add_argument('--review-after-minutes', type=float, default=10)
    parser.add_argument('--min-free-disk-gb', type=float, default=8)
    return parser.parse_args()


def blocking_tickets(ticket_text, own_number):
    """Ticket numbers on the first 'Blocked by' line, without the ticket's own number."""
    line = next((line for line in ticket_text.splitlines() if BLOCKED_BY_LINE.search(line)), '')
    return [number for number in re.findall(r'\b(\d{1,3})\b', line) if number != own_number]


def ticket_entries(tickets_directory, run_directory, prefix):
    entries = {}
    for path in sorted(tickets_directory.glob('*.md')):
        match = TICKET_NUMBER.match(path.name)
        if not match:
            continue
        number = match.group(1)
        entries[number] = {
            'file': str(path), 'depends_on': blocking_tickets(path.read_text(), number), 'scope': TO_FILL,
            'status': 'pending', 'agent_name': f'{prefix}t{number}', 'handoff': f'{run_directory}/handoffs/t{number}.md',
            'candidate_branch': f'{prefix.rstrip("-")}/i{number}-candidate',
        }
    return entries


def starter_ledger(arguments, run_directory, repository, base_sha):
    namespace = arguments.prefix.rstrip('-')
    base_moved_check = (f'test "$(git -C {repository} rev-parse {arguments.base_branch})" = {base_sha} '
                        f'|| echo "base moved: $(git -C {repository} rev-parse {arguments.base_branch})"')
    return {
        'run': str(run_directory), 'repository': str(repository), 'spec': str(arguments.spec.resolve()),
        'tickets_directory': str(arguments.tickets.resolve()),
        'base_branch': arguments.base_branch, 'base_sha': base_sha,
        'config': {'agent_name_prefix': arguments.prefix, 'herdr_workspace': arguments.workspace,
                   'max_workers': 4, 'max_integrators': 1, 'permission_mode': TO_FILL,
                   'model': 'claude-opus-5-5', 'model_marker': 'Opus 5.5', 'review_skill': TO_FILL, 'reviewer': 'codex',
                   'branch_pattern': f'{namespace}/t{{ticket}}', 'candidate_branch_pattern': f'{namespace}/i{{ticket}}-candidate',
                   'worktree_pattern': f'{repository}-{arguments.prefix}t{{ticket}}',
                   'recovery_prefix': f'refs/orchestrate/{run_directory.name}',
                   'min_free_disk_gb': arguments.min_free_disk_gb},
        'commands': {'worktree_create': 'git worktree add -b {branch} {path} {base}', 'worktree_facts': {},
                     'worktree_start': None, 'worktree_remove': 'git worktree remove {path}'},
        'decisions': [], 'shared_interfaces': {},
        'validation': {'test_command': TO_FILL, 'ticket_checks': TO_FILL, 'integration_fast_checks': TO_FILL,
                       'integration_budget_seconds': 60, 'final_full_validation': TO_FILL,
                       'worktree_runtime_cleanup': TO_FILL, 'must_contain': {'test_command': []}},
        'heavy_jobs': {'slots': 1, 'review_after_minutes': arguments.review_after_minutes,
                       'lock': f'{run_directory}/heavy-job.lock', 'stop_cleanup': TO_FILL,
                       'memory_probe': TO_FILL, 'sizing': TO_FILL},
        'resource_watch': {'every_minutes': 2, 'idle_shell_minutes': 30, 'checks': [
            {'name': 'disk-gb', 'command': f"df -g {run_directory} | awk 'NR==2 {{print $4}}'",
             'minimum': arguments.min_free_disk_gb},
            {'name': 'base', 'command': base_moved_check, 'match': 'base moved'},
        ]},
        'integration': {'branch': TO_FILL, 'worktree': TO_FILL, 'last_validated_sha': base_sha,
                        'lock': f'{run_directory}/integration.lock', 'owner': None},
        'tickets': ticket_entries(arguments.tickets.resolve(), run_directory, arguments.prefix),
        'jobs': {}, 'events': [], 'open_items_for_user': [],
        'resources': {'sessions': [], 'worktrees': [], 'branches': [], 'recovery_refs': []},
    }


def keys_to_fill(value, path=''):
    if value == TO_FILL:
        return [path]
    if isinstance(value, dict):
        return [found for key, child in value.items() for found in keys_to_fill(child, f'{path}.{key}' if path else key)]
    return []


def main():
    arguments = parse_arguments()
    run_directory, repository = arguments.run.resolve(), arguments.repository.resolve()
    ledger_path = run_directory / 'ledger.json'
    if ledger_path.exists():
        sys.exit(f'{ledger_path} exists; this script only starts a new run')
    result = subprocess.run(['git', '-C', str(repository), 'rev-parse', '--verify', f'{arguments.base_branch}^{{commit}}'],
                            capture_output=True, text=True)
    if result.returncode:
        sys.exit(f'cannot resolve the base branch {arguments.base_branch}: {result.stderr.strip()}')
    ledger = starter_ledger(arguments, run_directory, repository, result.stdout.strip())
    if not ledger['tickets']:
        sys.exit(f'no ticket files that start with a number in {arguments.tickets}')
    for folder in RUN_FOLDERS:
        (run_directory / folder).mkdir(parents=True, exist_ok=True)
    for template in STARTER_TEMPLATES.glob('*.md'):
        shutil.copy(template, run_directory / 'assignments/templates' / template.name)
    ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + '\n')
    print(ledger_path)
    print('fill: ' + ', '.join(keys_to_fill(ledger)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
