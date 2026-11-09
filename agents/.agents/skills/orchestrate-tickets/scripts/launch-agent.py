#!/usr/bin/env python3
"""Start a delegated Claude Code session in a new muted Herdr tab and record it in the ledger.

Usage: launch-agent.py --ledger <ledger.json> --workspace <herdr-workspace> --cwd <worktree>
                       --name <agent-name> --role <role> --permission-mode <mode> [--model <model>]

Order, write-ahead: create the tab with --no-focus, record pane and tab under
ledger.resources.sessions (status "starting"), mute the pane, start Claude with the pinned
model, prompt suggestions off, and the session label <agent-name>, then record the
session ID (status "live"). Prints the record as JSON.
The caller still checks the model that the session shows before it assigns work.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ledger', required=True, type=Path)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--cwd', required=True, type=Path)
    parser.add_argument('--name', required=True, help='Herdr agent name; starts with the run prefix that watch-run.py uses')
    parser.add_argument('--role', required=True, help='ledger role, for example a ticket ID, i07-1, or f01')
    parser.add_argument('--permission-mode', required=True, help='the mode the user approved for the run')
    parser.add_argument('--model', default='claude-opus-5-5')
    return parser.parse_args()


def herdr(arguments):
    result = subprocess.run(['herdr', *arguments], capture_output=True, text=True)
    if result.returncode:
        sys.exit(f'herdr {arguments[0]} {arguments[1]} failed; inspect the live state before a retry:\n{result.stdout}{result.stderr}')
    return json.loads(result.stdout)['result'] if result.stdout.strip() else None


def update_session(ledger_path, pane_id, record):
    ledger = json.loads(ledger_path.read_text())
    sessions = ledger.setdefault('resources', {}).setdefault('sessions', [])
    existing = next((session for session in sessions if session.get('pane_id') == pane_id), None)
    if existing is None:
        sessions.append(record)
    else:
        existing.update(record)
    temporary = ledger_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(ledger_path)


def main():
    arguments = parse_arguments()
    if os.environ.get('HERDR_ENV') != '1':
        sys.exit('HERDR_ENV=1 is missing: run this inside Herdr')
    worktree = arguments.cwd.resolve()
    if not worktree.is_dir():
        sys.exit(f'no directory: {worktree}')
    created = herdr(['tab', 'create', '--workspace', arguments.workspace, '--cwd', str(worktree),
                     '--label', arguments.name, '--no-focus'])
    pane_id = created['root_pane']['pane_id']
    record = {'name': arguments.name, 'role': arguments.role, 'pane_id': pane_id, 'tab_id': created['tab']['tab_id'],
              'worktree': str(worktree), 'model': arguments.model, 'status': 'starting'}
    update_session(arguments.ledger, pane_id, record)
    herdr(['pane', 'report-metadata', pane_id, '--source', 'dotfiles:pane-mute', '--token', 'dotfiles_pane_mute=1'])
    started = herdr(['agent', 'start', arguments.name, '--kind', 'claude', '--pane', pane_id, '--timeout', '90000', '--',
                     '--model', arguments.model, '--permission-mode', arguments.permission_mode,
                     '--settings', '{"promptSuggestionEnabled": false}', '--name', arguments.name])
    agent = started['agent']
    record.update(status='live', session_id=agent['agent_session']['value'], cwd=agent['cwd'],
                  started_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    update_session(arguments.ledger, pane_id, record)
    print(json.dumps(record, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
