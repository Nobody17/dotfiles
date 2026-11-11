#!/usr/bin/env python3
"""Dispatch one frontier ticket: worktree, ledger record, assignment, worker session, bootstrap prompt.

Usage: dispatch-worker.py --ledger <ledger.json> --ticket <id>
       dispatch-worker.py --ledger <ledger.json> --ticket <id> --send-ticket

Order, write-ahead:
  1. Refuse a ticket that is not pending, or whose blockers are not integrated, or when the integration
     worktree is not at ledger.integration.last_validated_sha.
  2. Record status working, branch, worktree and start_sha in the ledger.
  3. Create the worktree (commands.worktree_create), store commands.worktree_facts, run commands.worktree_start.
  4. Render <run>/assignments/templates/worker.md to <run>/assignments/t<id>.md.
  5. Launch the worker (launch-agent.py), check config.model_marker on its screen, send the bootstrap prompt.
A failure after step 2 records the ticket as blocked with the reason and its previous stage.
After the worker's ready message, --send-ticket sends the ticket file path as its task message.
run_steps.py lists the ledger keys.
"""
import argparse
import sys
from pathlib import Path

import run_steps
from run_steps import StepRefused


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ledger', required=True, type=Path)
    parser.add_argument('--ticket', required=True)
    parser.add_argument('--send-ticket', action='store_true', help='send the ticket path to the ready worker')
    return parser.parse_args()


def open_blockers(ledger, ticket_id):
    tickets = ledger['tickets']
    return [blocker for blocker in tickets[ticket_id].get('depends_on', [])
            if tickets.get(blocker, {}).get('status') != 'integrated']


def check_frontier(ledger, ticket_id):
    ticket = ledger['tickets'].get(ticket_id)
    if ticket is None:
        raise StepRefused(f'no ticket {ticket_id} in the ledger')
    if ticket['status'] != 'pending':
        raise StepRefused(f'ticket {ticket_id} is {ticket["status"]}, not pending')
    blockers = open_blockers(ledger, ticket_id)
    if blockers:
        raise StepRefused(f'ticket {ticket_id} waits for {", ".join(blockers)}')
    integration = ledger['integration']
    tip = run_steps.git(integration['worktree'], 'rev-parse', 'HEAD')
    if tip != integration['last_validated_sha']:
        raise StepRefused(f'integration worktree is at {tip}, the ledger validated {integration["last_validated_sha"]}')
    return tip


def create_worktree(ledger, names, start_sha):
    commands = ledger['commands']
    output = run_shell_filled(commands['worktree_create'], ledger['repository'], 'worktree_create',
                              branch=names['branch'], base=start_sha, path=names['worktree'])
    if commands.get('worktree_start'):
        run_steps.run_shell(commands['worktree_start'], names['worktree'], 'worktree_start')
    return run_steps.captured_facts(commands.get('worktree_facts'), output)


def run_shell_filled(template, directory, purpose, **values):
    return run_steps.run_shell(run_steps.fill(template, **values), directory, purpose)


def dispatch(ledger_path, ticket_id):
    ledger = run_steps.read_ledger(ledger_path)
    start_sha = check_frontier(ledger, ticket_id)
    names = run_steps.ticket_names(ledger, ticket_id)
    run_directory = ledger_path.parent

    def record_start(ledger):
        ledger['tickets'][ticket_id].update(status='working', start_sha=start_sha, branch=names['branch'],
                                            worktree=names['worktree'])
        resources = ledger.setdefault('resources', {})
        resources.setdefault('worktrees', []).append({'path': names['worktree'], 'branch': names['branch'], 'status': 'live'})
        resources.setdefault('branches', []).append({'name': names['branch'], 'tip': start_sha})
        ledger.setdefault('events', []).append(f'dispatch {ticket_id} at {start_sha[:8]}')
    run_steps.update_ledger(ledger_path, record_start)

    try:
        facts = create_worktree(ledger, names, start_sha)
        run_steps.update_ledger(ledger_path, lambda ledger: ledger['tickets'][ticket_id].update(facts))
        assignment = run_directory / 'assignments' / f't{ticket_id}.md'
        run_steps.render_assignment(ledger_path, run_directory / 'assignments/templates/worker.md', assignment,
                                    ticket_id, {'ticket_id': ticket_id})
        run_steps.start_session(
            ledger_path, name=ledger['tickets'][ticket_id]['agent_name'], role=ticket_id, directory=names['worktree'],
            role_instructions=run_steps.REFERENCES / 'worker.md', assignment=assignment,
            closing_sentence='Send the ready message as a file; the ticket path comes next.')
    except StepRefused as error:
        def record_block(ledger):
            ledger['tickets'][ticket_id].update(status='blocked', blocked={'previous': 'working', 'reason': str(error)})
        run_steps.update_ledger(ledger_path, record_block)
        raise
    print(f'dispatched {ticket_id}: {names["worktree"]} at {start_sha}; assignment {assignment}')


def send_ticket(ledger_path, ticket_id):
    ticket = run_steps.read_ledger(ledger_path)['tickets'][ticket_id]
    run_steps.herdr('agent', 'prompt', ticket['agent_name'], ticket['file'])
    print(f'sent {ticket["file"]} to {ticket["agent_name"]}')


def main():
    arguments = parse_arguments()
    ledger_path = arguments.ledger.resolve()
    try:
        if arguments.send_ticket:
            send_ticket(ledger_path, arguments.ticket)
        else:
            dispatch(ledger_path, arguments.ticket)
    except StepRefused as error:
        return run_steps.fail(error)
    return 0


if __name__ == '__main__':
    sys.exit(main())
