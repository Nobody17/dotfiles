#!/usr/bin/env python3
"""Print the last replies of a delegated Claude Code session from its transcript.

Usage: last-reply.py --ledger <ledger.json> --name <agent-name> [--count N]
       last-reply.py --session-id <id> [--count N]

The transcript is ~/.claude/projects/<cwd slug>/<session-id>.jsonl; launch-agent.py
records the session ID under ledger.resources.sessions. The output gives the last N
assistant texts with their times, and the time and kind of the last transcript entry.
A dialog, an API error, or a prompt that waits for input shows only on the screen:
read the pane for those.
"""
import argparse
import json
import sys
from pathlib import Path

PROJECTS = Path.home() / '.claude' / 'projects'


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--name', help='agent name in ledger.resources.sessions (needs --ledger)')
    source.add_argument('--session-id')
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--count', type=int, default=1)
    return parser.parse_args()


def session_id_from_ledger(ledger_path, name):
    sessions = json.loads(ledger_path.read_text()).get('resources', {}).get('sessions', [])
    matches = [session for session in sessions if session.get('name') == name and session.get('session_id')]
    if not matches:
        sys.exit(f'no session with a session_id for {name} in {ledger_path}')
    return matches[-1]['session_id']


def assistant_texts(records):
    for record in records:
        message = record.get('message') or {}
        content = message.get('content')
        if record.get('type') != 'assistant' or not isinstance(content, list):
            continue
        text = '\n'.join(part['text'] for part in content if isinstance(part, dict) and part.get('type') == 'text').strip()
        if text:
            yield record.get('timestamp', '?'), text


def last_entry(records):
    for record in reversed(records):
        if record.get('timestamp'):
            message = record.get('message') or {}
            content = message.get('content')
            parts = [part.get('type') for part in content if isinstance(part, dict)] if isinstance(content, list) else []
            return f"{record['timestamp']} {record.get('type')} {'/'.join(parts)}".strip()
    return 'none'


def main():
    arguments = parse_arguments()
    if arguments.name and not arguments.ledger:
        sys.exit('--name needs --ledger')
    session_id = arguments.session_id or session_id_from_ledger(arguments.ledger, arguments.name)
    transcripts = sorted(PROJECTS.glob(f'*/{session_id}.jsonl'))
    if not transcripts:
        sys.exit(f'no transcript for session {session_id} under {PROJECTS}')
    records = [json.loads(line) for line in transcripts[-1].read_text().splitlines() if line.strip()]
    for timestamp, text in list(assistant_texts(records))[-arguments.count:]:
        print(f'--- {timestamp}\n{text}\n')
    print(f'last entry: {last_entry(records)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
