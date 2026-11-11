#!/usr/bin/env python3
"""Start the integration of one reviewed ticket: lock, ledger record, assignment, integrator session.

Usage: start-integration.py --ledger <ledger.json> --ticket <id> --submitted <sha> [--handoff <file>]
                            [--attempt N] [--note <text>]

Run it after you verified the worker handoff. Order, write-ahead:
  1. Refuse when the ticket branch is not at --submitted, the ticket worktree is dirty, or the integration
     worktree is not at ledger.integration.last_validated_sha.
  2. Take the exclusive slot: create <run>/integration.lock (atomic; an existing lock refuses the start)
     and write its owner file (job, agent, integration SHA).
  3. Record the job i<id>-<attempt>, the ticket status integrating and submitted_sha in the ledger.
  4. Render <run>/assignments/templates/integrator.md to <run>/assignments/<job>.md; --note is appended as
     a section "Addition from the orchestrator" (expected conflicts, test files to include).
  5. Launch the integrator in the integration worktree, check config.model_marker, send the bootstrap prompt.
A failure after step 2 keeps the lock: inspect, then remove the lock yourself or run the script again
after `rmdir`. run_steps.py lists the ledger keys.
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
    parser.add_argument('--submitted', required=True, help='the submitted commit of the worker handoff')
    parser.add_argument('--handoff', type=Path, help='worker handoff file; default is the ticket entry\'s handoff')
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--note', help='text for the integrator, appended to its assignment')
    return parser.parse_args()


def job_names(ledger, ticket_id, attempt):
    job = f'i{ticket_id}-{attempt}'
    agent = f'{ledger["config"]["agent_name_prefix"]}i{ticket_id}' + ('' if attempt == 1 else f'-{attempt}')
    return job, agent


def check_submission(ledger, ticket_id, submitted):
    ticket = ledger['tickets'].get(ticket_id)
    if ticket is None or ticket['status'] not in ('working', 'reviewed'):
        raise StepRefused(f'ticket {ticket_id} is not working or reviewed')
    submitted_sha = run_steps.git(ledger['repository'], 'rev-parse', '--verify', f'{submitted}^{{commit}}')
    branch_tip = run_steps.git(ledger['repository'], 'rev-parse', f'refs/heads/{ticket["branch"]}')
    if branch_tip != submitted_sha:
        raise StepRefused(f'{ticket["branch"]} is at {branch_tip}, the handoff submitted {submitted_sha}')
    if not run_steps.worktree_is_clean(ticket['worktree']):
        raise StepRefused(f'{ticket["worktree"]} has uncommitted changes')
    integration = ledger['integration']
    tip = run_steps.git(integration['worktree'], 'rev-parse', 'HEAD')
    if tip != integration['last_validated_sha']:
        raise StepRefused(f'integration worktree is at {tip}, the ledger validated {integration["last_validated_sha"]}')
    return submitted_sha, tip


def take_lock(lock, job, agent, integration_sha):
    try:
        lock.mkdir()
    except FileExistsError:
        owner = (lock / 'owner').read_text().strip() if (lock / 'owner').exists() else 'no owner file'
        raise StepRefused(f'the integration slot is occupied: {owner}') from None
    (lock / 'owner').write_text(f'job {job}\nagent {agent}\nintegration_sha {integration_sha}\n')


def start(arguments, ledger_path):
    ledger = run_steps.read_ledger(ledger_path)
    ticket_id = arguments.ticket
    submitted_sha, integration_sha = check_submission(ledger, ticket_id, arguments.submitted)
    job, agent = job_names(ledger, ticket_id, arguments.attempt)
    run_directory = ledger_path.parent
    handoff = arguments.handoff or Path(ledger['tickets'][ticket_id]['handoff'])
    take_lock(Path(ledger['integration']['lock']), job, agent, integration_sha)

    def record_job(ledger):
        ledger['tickets'][ticket_id].update(status='integrating', submitted_sha=submitted_sha, handoff_current=str(handoff))
        ledger['integration']['owner'] = job
        ledger.setdefault('jobs', {})[job] = {
            'ticket': ticket_id, 'agent': agent, 'status': 'running', 'integration_sha_at_start': integration_sha,
            'handoff': f'{run_directory}/handoffs/{job}.md'}
        ledger.setdefault('events', []).append(f'{ticket_id} reviewed ({submitted_sha[:8]}); lock -> {job}')
    run_steps.update_ledger(ledger_path, record_job)

    assignment = run_directory / 'assignments' / f'{job}.md'
    run_steps.render_assignment(ledger_path, run_directory / 'assignments/templates/integrator.md', assignment, ticket_id,
                                {'ticket_id': ticket_id, 'job_id': job, 'agent_name': agent, 'integration_sha': integration_sha})
    if arguments.note:
        with assignment.open('a') as file:
            file.write(f'\n## Addition from the orchestrator\n{arguments.note}\n')
    run_steps.start_session(
        ledger_path, name=agent, role=job, directory=ledger['integration']['worktree'],
        role_instructions=run_steps.REFERENCES / 'integrator.md', assignment=assignment,
        closing_sentence='Write the handoff file and reply with its path.')
    print(f'started {job} ({agent}) at {integration_sha}; assignment {assignment}')


def main():
    arguments = parse_arguments()
    try:
        start(arguments, arguments.ledger.resolve())
    except StepRefused as error:
        return run_steps.fail(error)
    return 0


if __name__ == '__main__':
    sys.exit(main())
