#!/usr/bin/env python3
"""Finish one accepted integration: ledger, sessions, lock, worktree, branches.

Usage: finish-integration.py --ledger <ledger.json> --ticket <id> --integrated <sha> [--attempt N]
                             [--close-tab <herdr tab>]... [--accounted]

Run it after you read the integrator handoff and verified its checks. Each step runs only when its work
is still open, so a rerun after a refusal continues where the last run stopped:
  1. Refuse when the integration worktree is not at --integrated, is dirty, or has an unfinished Git
     operation; the same for the ticket worktree while it exists.
  2. Record the ticket as integrated, the job as done and the new last_validated_sha in the ledger.
  3. Close the Herdr tabs of the worker and the integrator (ledger sessions with their roles) and each
     --close-tab (reviewer tabs from the handoffs). Refuse to go on while a process still uses the ticket worktree.
  4. Release the integration slot (the lock must name this job).
  5. Remove the ticket worktree and its runtime resources (commands.worktree_remove).
  6. Retire the ticket branch and the candidate branch with retire-resources.py. A branch whose patch the
     integrator changed is refused: compare `git range-diff <start>..<submitted> <integrated>^..<integrated>`
     with the integration handoff, then run this script again with --accounted.
run_steps.py lists the ledger keys.
"""
import argparse
import subprocess
import sys
from pathlib import Path

import run_steps
from run_steps import StepRefused


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ledger', required=True, type=Path)
    parser.add_argument('--ticket', required=True)
    parser.add_argument('--integrated', required=True, help='the integrated commit of the integrator handoff')
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--close-tab', action='append', default=[], metavar='TAB', help='reviewer tab to close')
    parser.add_argument('--accounted', action='store_true',
                        help='you checked the range-diff of a ticket patch that the integrator changed')
    return parser.parse_args()


def check_worktree(worktree, purpose):
    if not run_steps.worktree_is_clean(worktree):
        raise StepRefused(f'{purpose} worktree {worktree} has uncommitted changes')
    unfinished = run_steps.unfinished_operations(worktree)
    if unfinished:
        raise StepRefused(f'{purpose} worktree {worktree} has an unfinished Git operation: {", ".join(unfinished)}')


def check_result(ledger, ticket, integrated_sha):
    integration = ledger['integration']
    tip = run_steps.git(integration['worktree'], 'rev-parse', 'HEAD')
    if tip != integrated_sha and ticket['status'] != 'integrated':
        raise StepRefused(f'integration worktree is at {tip}, not at {integrated_sha}')
    if ticket['status'] == 'integrated' and ticket.get('integrated_sha') != integrated_sha:
        raise StepRefused(f'the ledger integrated ticket at {ticket.get("integrated_sha")}, not at {integrated_sha}')
    check_worktree(integration['worktree'], 'integration')
    if Path(ticket['worktree']).exists():
        check_worktree(ticket['worktree'], 'ticket')


def release_lock(lock, job):
    if not lock.exists():
        return
    owner = (lock / 'owner').read_text() if (lock / 'owner').exists() else ''
    if f'job {job}\n' not in owner:
        raise StepRefused(f'the integration lock names another owner: {owner.strip() or "no owner file"}')
    (lock / 'owner').unlink()
    lock.rmdir()


def remove_worktree(ledger_path, ledger, ticket):
    if not Path(ticket['worktree']).exists():
        return
    run_steps.run_shell(run_steps.fill(ledger['commands']['worktree_remove'], path=ticket['worktree']),
                        ledger['repository'], 'worktree_remove')

    def record(ledger):
        for worktree in ledger.get('resources', {}).get('worktrees', []):
            if worktree['path'] == ticket['worktree']:
                worktree['status'] = 'removed'
    run_steps.update_ledger(ledger_path, record)


def retire_branches(ledger, ticket, candidate_branch, integrated_sha, accounted):
    repository, integration = ledger['repository'], ledger['integration']
    proof = f'{ticket["branch"]}={ticket["start_sha"]}:{integrated_sha}'
    command = [sys.executable, str(run_steps.SCRIPTS / 'retire-resources.py'), '--repo', repository,
               '--destination', integration['branch'], '--destination-sha', integrated_sha,
               '--recovery-prefix', ledger['config']['recovery_prefix'],
               '--branch', f'{ticket["branch"]}={ticket["submitted_sha"]}', '--squash', proof]
    if accounted:
        command += ['--accounted', proof]
    candidate_tip = run_steps.git(repository, 'rev-parse', '--verify', '--quiet', f'refs/heads/{candidate_branch}', check=False)
    if candidate_tip:
        command += ['--branch', f'{candidate_branch}={candidate_tip}']
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise StepRefused(f'branches stay: {result.stderr.strip()}')
    return result.stdout


def finish(arguments, ledger_path):
    ticket_id, attempt = arguments.ticket, arguments.attempt
    job = f'i{ticket_id}-{attempt}'
    ledger = run_steps.read_ledger(ledger_path)
    ticket = ledger['tickets'][ticket_id]
    integrated_sha = run_steps.git(ledger['repository'], 'rev-parse', '--verify', f'{arguments.integrated}^{{commit}}')
    check_result(ledger, ticket, integrated_sha)

    def record_integration(ledger):
        ledger['tickets'][ticket_id].update(status='integrated', integrated_sha=integrated_sha,
                                            integration_handoff=ledger['jobs'][job]['handoff'])
        ledger['jobs'][job]['status'] = 'done'
        ledger['integration'].update(last_validated_sha=integrated_sha, owner=None)
        ledger.setdefault('events', []).append(f'{ticket_id} integrated at {integrated_sha[:8]}')
    if ticket['status'] != 'integrated':
        run_steps.update_ledger(ledger_path, record_integration)

    closed = run_steps.close_sessions(ledger_path, {ticket_id, job}, arguments.close_tab)
    if Path(ticket['worktree']).exists():
        processes = run_steps.wait_for_no_process(ticket['worktree'])
        if processes:
            raise StepRefused('processes still use the ticket worktree; run this script again when they ended:\n'
                              + '\n'.join(processes))
    release_lock(Path(ledger['integration']['lock']), job)
    ledger = run_steps.read_ledger(ledger_path)
    ticket = ledger['tickets'][ticket_id]
    remove_worktree(ledger_path, ledger, ticket)
    names = run_steps.ticket_names(ledger, ticket_id)
    report = retire_branches(ledger, ticket, names['candidate_branch'], integrated_sha, arguments.accounted)
    run_steps.update_ledger(ledger_path, lambda ledger: ledger.setdefault('events', []).append(
        f'{ticket_id} resources retired' + (' (changed patch accounted)' if arguments.accounted else '')))
    print(f'finished {ticket_id} at {integrated_sha}; closed {", ".join(closed) or "no session"}')
    print(report)


def main():
    arguments = parse_arguments()
    try:
        finish(arguments, arguments.ledger.resolve())
    except StepRefused as error:
        return run_steps.fail(error)
    return 0


if __name__ == '__main__':
    sys.exit(main())
