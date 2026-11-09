#!/usr/bin/env python3
"""Wait for run events: new handoff and message files, lifecycle changes of the run's Herdr agents, and resource alarms.

Usage: watch-run.py <run-directory> --prefix <agent-name-prefix> [--once] [--timeout-minutes N]

Prints one line per event:
  handoff <file>                   a new file in <run>/handoffs/
  message <file>                   a new file in <run>/messages/ (see references/messages.md)
  agent <name> <old>-><new>        an agent reached idle, done, blocked, or unknown
  agent <name> gone                an agent left `herdr agent list`
  agent <name> <idle|done> <N> min with <K> shells
                                   a resting agent still has running shells (background commands)
                                   after resource_watch.idle_shell_minutes (default 30)
  resource <check> <value> below <minimum>
                                   a minimum check fell below its minimum
  resource <check> new: <line>     a match check printed a new matching line, such as an OOM kill
  resource <check> failed: <error> a check command failed or printed no number
  job <job> <label> needs a review: running <N> min, last output <M> min ago
                                   a heavy-job.py job passed its review time; it continues
                                   until a reviewer runs heavy-job.py --extend or --stop
  job <job> <label> left by ended wrapper; group <G> can still run
                                   a heavy-job.py wrapper died; its record stays until you delete it
  job <job> <label> cleanup failed; slot held until --stop or --release
                                   a stopped job's stop_cleanup failed
  timeout after <N> min            no event within --timeout-minutes
  herdr unavailable: <error>       `herdr agent list` failed three polls in a row

--once prints all events of the first poll that has events, then exits 0.
<run>/watch-state.json keeps the seen files, agent states, and alarm states between calls,
so the next call reports an event that occurred between two calls, and an alarm only once.
The first call, without a state file, takes the existing files as seen; the first run of a
match check takes its existing lines as seen.

Resource checks come from ledger.resource_watch in <run>/ledger.json, read again before each round:
  {"every_minutes": 2, "idle_shell_minutes": 30,
   "checks": [{"name": "disk-gb", "command": "df -g / | awk 'NR==2 {print $4}'", "minimum": 8},
              {"name": "oom", "command": "<kernel log command>", "match": "Killed process"}]}
A minimum check prints a number as the first word of its output. A match check prints lines;
"match" is a Python regular expression. Each command runs in a shell with a 90 s limit.
"""
import argparse
import datetime
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

SETTLED_STATES = {'idle', 'done', 'blocked', 'unknown'}
RESTING_STATES = {'idle', 'done'}
WATCHED_DIRECTORIES = {'handoffs': 'handoff', 'messages': 'message'}
POLL_SECONDS = 15
FAILURES_BEFORE_EXIT = 3
DEFAULT_CHECK_MINUTES = 2
DEFAULT_IDLE_SHELL_MINUTES = 30
CHECK_LIMIT_SECONDS = 90
COMMAND_LIMIT_SECONDS = 30
SHELL_COMMAND = re.compile(r'^(?:\S*/)?(?:zsh|bash|sh|fish) (?:-\S+ )*-c ')


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('run_directory', type=Path)
    parser.add_argument('--prefix', required=True, help='name prefix of the run agents, for example nb-')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--timeout-minutes', type=float)
    return parser.parse_args()


def watched_files(run_directory):
    return {f'{directory}/{path.name}' for directory in WATCHED_DIRECTORIES
            for path in (run_directory / directory).glob('*.md')}


def load_state(state_path, run_directory):
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    return {
        'files': set(state['files']) if 'files' in state else watched_files(run_directory),
        'agents': state.get('agents', {}),
        'checks': state.get('checks', {}),
        'idle': state.get('idle', {}),
        'jobs_reported': state.get('jobs_reported', []),
        'last_check': state.get('last_check', 0),
    }


def save_state(state_path, state):
    temporary = state_path.with_suffix('.tmp')
    temporary.write_text(json.dumps({**state, 'files': sorted(state['files'])}, indent=2) + '\n')
    temporary.replace(state_path)


def file_events(run_directory, seen_files):
    new_files = sorted(watched_files(run_directory) - seen_files)
    events = []
    for relative_path in new_files:
        directory, name = relative_path.split('/', 1)
        events.append(f'{WATCHED_DIRECTORIES[directory]} {name}')
    return events, seen_files | set(new_files)


def run_agent_states(prefix):
    try:
        result = subprocess.run(['herdr', 'agent', 'list'], capture_output=True, text=True,
                                timeout=COMMAND_LIMIT_SECONDS)
    except subprocess.TimeoutExpired:
        return None, f'no answer within {COMMAND_LIMIT_SECONDS} s'
    if result.returncode:
        return None, result.stderr.strip()[:200]
    agents = json.loads(result.stdout)['result']['agents']
    return {agent['name']: agent['agent_status'] for agent in agents if (agent.get('name') or '').startswith(prefix)}, ''


def agent_events(previous_states, current_states):
    events = []
    for name, status in sorted(current_states.items()):
        previous = previous_states.get(name, 'new')
        if status != previous and status in SETTLED_STATES:
            events.append(f'agent {name} {previous}->{status}')
    events += [f'agent {name} gone' for name in sorted(set(previous_states) - set(current_states))]
    return events


def watch_policy(run_directory):
    ledger_path = run_directory / 'ledger.json'
    try:
        return json.loads(ledger_path.read_text()).get('resource_watch') or {}
    except (OSError, json.JSONDecodeError):
        return {}


def process_table():
    """Return [(pid, parent pid, command)] of all processes."""
    try:
        result = subprocess.run(['ps', '-axo', 'pid=,ppid=,command='], capture_output=True, text=True,
                                timeout=COMMAND_LIMIT_SECONDS)
    except subprocess.TimeoutExpired:
        return []
    table = []
    for line in result.stdout.splitlines():
        fields = line.split(None, 2)
        if len(fields) == 3 and fields[0].isdigit() and fields[1].isdigit():
            table.append((int(fields[0]), int(fields[1]), fields[2]))
    return table


def started_with_name(command, agent_name):
    try:
        words = shlex.split(command)
    except ValueError:
        words = command.split()
    return any(word == '--name' and value == agent_name for word, value in zip(words, words[1:]))


def running_shells(table, agent_name):
    """Count the shell children of the Claude process that launch-agent.py started with --name <agent_name>."""
    agent_pids = {pid for pid, _parent, command in table
                  if 'claude' in command.split(' ', 1)[0] and started_with_name(command, agent_name)}
    return sum(1 for _pid, parent, command in table if parent in agent_pids and SHELL_COMMAND.match(command))


def idle_shell_events(idle_state, agent_states, shell_counts, now, limit_seconds):
    """Report each resting period of an agent with running shells once, after limit_seconds."""
    events, next_state = [], {}
    for name, status in sorted(agent_states.items()):
        shells = shell_counts.get(name, 0)
        if status not in RESTING_STATES or shells == 0:
            continue
        entry = dict(idle_state.get(name) or {'since': now, 'reported': False})
        if not entry['reported'] and now - entry['since'] >= limit_seconds:
            events.append(f'agent {name} {status} {(now - entry["since"]) / 60:.0f} min with {shells} shells')
            entry['reported'] = True
        next_state[name] = entry
    return events, next_state


def minimum_event(check, output, was_below):
    """Return (event or None, below now) for a minimum check."""
    words = output.split()
    try:
        value = float(words[0])
    except (IndexError, ValueError):
        return f'resource {check["name"]} failed: no number in output {output.strip()[:80]!r}', was_below
    below = value < check['minimum']
    event = f'resource {check["name"]} {value:g} below {check["minimum"]:g}' if below and not was_below else None
    return event, below


def match_events(check, output, seen_lines):
    """Return (events, seen lines). seen_lines None means first run: take all lines as seen.
    The seen lines are the matching lines of the current output, so they stay as small as the log."""
    pattern = re.compile(check['match'])
    matching = [line.strip() for line in output.splitlines() if pattern.search(line)]
    if seen_lines is None:
        return [], matching
    seen = set(seen_lines)
    events = [f'resource {check["name"]} new: {line[:200]}' for line in matching if line not in seen]
    return events, matching


def run_check_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=CHECK_LIMIT_SECONDS)
    except subprocess.TimeoutExpired:
        return None, f'no result within {CHECK_LIMIT_SECONDS} s'
    if result.returncode:
        return None, f'exit {result.returncode}: {(result.stderr or result.stdout).strip()[:120]}'
    return result.stdout, ''


def resource_events(checks, check_state, run_command):
    """Run each check once. check_state maps a check name to {below, seen, failing}."""
    events, next_state = [], {}
    for check in checks:
        name = check.get('name', '?')
        previous = check_state.get(name, {})
        output, error = run_command(check.get('command', 'false'))
        if output is None:
            if not previous.get('failing'):
                events.append(f'resource {name} failed: {error}')
            next_state[name] = {**previous, 'failing': True}
            continue
        entry = {**previous, 'failing': False}
        if 'match' in check:
            new_events, entry['seen'] = match_events(check, output, previous.get('seen'))
            events += new_events
        elif 'minimum' in check:
            event, entry['below'] = minimum_event(check, output, previous.get('below', False))
            events += [event] if event else []
        next_state[name] = entry
    return events, next_state


def process_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def minutes_since(timestamp_text, now):
    return (now - datetime.datetime.fromisoformat(timestamp_text).timestamp()) / 60


def job_events(run_directory, reported, now):
    """Check the records of heavy-job.py. Each alarm is reported once per key in `reported`.
    Returns (events, keys of the alarms that still hold)."""
    events, still_reported = [], []

    def report_once(key, event):
        if key not in reported:
            events.append(event)
        still_reported.append(key)

    for path in sorted((run_directory / 'heavy-jobs').glob('*.json')):
        if '.request-' in path.name:
            continue
        try:
            record = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        job, label = record.get('job', path.stem), record.get('label', '?')
        if not process_alive(record.get('pid', 0)):
            report_once(f'ended:{job}', f'job {job} {label} left by ended wrapper; '
                                        f'group {record.get("process_group")} can still run')
            continue
        if record.get('state') == 'cleanup failed':
            attempts = record.get('cleanup_attempts', 1)
            report_once(f'cleanup:{job}:{attempts}',
                        f'job {job} {label} cleanup failed (attempt {attempts}); slot held until --stop or --release')
            continue
        if minutes_since(record['review_at'], now) > 0:
            report_once(f'{job}@{record["review_at"]}',
                        f'job {job} {label} needs a review: running {minutes_since(record["started"], now):.0f} min, '
                        f'last output {minutes_since(record["last_output"], now):.0f} min ago')
    return events, still_reported


def poll_resources(run_directory, state, agent_states, now):
    policy = watch_policy(run_directory)
    events = []
    check_minutes = policy.get('every_minutes', DEFAULT_CHECK_MINUTES)
    if policy.get('checks') and now - state['last_check'] >= check_minutes * 60:
        check_events, state['checks'] = resource_events(policy['checks'], state['checks'], run_check_command)
        events += check_events
        state['last_check'] = now
    if any(status in RESTING_STATES for status in agent_states.values()):
        table = process_table()
        shell_counts = {name: running_shells(table, name) for name, status in agent_states.items()
                        if status in RESTING_STATES}
    else:
        shell_counts = {}
    idle_limit = policy.get('idle_shell_minutes', DEFAULT_IDLE_SHELL_MINUTES) * 60
    idle_events, state['idle'] = idle_shell_events(state['idle'], agent_states, shell_counts, now, idle_limit)
    job_alarms, state['jobs_reported'] = job_events(run_directory, state['jobs_reported'], now)
    return events + idle_events + job_alarms


def main():
    arguments = parse_arguments()
    run_directory = arguments.run_directory.resolve()
    state_path = run_directory / 'watch-state.json'
    state = load_state(state_path, run_directory)
    save_state(state_path, state)
    deadline = time.time() + arguments.timeout_minutes * 60 if arguments.timeout_minutes else None
    failures = 0
    while True:
        events, state['files'] = file_events(run_directory, state['files'])
        current_states, error = run_agent_states(arguments.prefix)
        if current_states is None:
            failures += 1
            if failures >= FAILURES_BEFORE_EXIT:
                events.append(f'herdr unavailable: {error}')
        else:
            failures = 0
            events += agent_events(state['agents'], current_states)
            state['agents'] = current_states
        events += poll_resources(run_directory, state, state['agents'], time.time())
        if not events and deadline and time.time() > deadline:
            events.append(f'timeout after {arguments.timeout_minutes:g} min')
        save_state(state_path, state)
        for event in events:
            print(event, flush=True)
        if events and arguments.once:
            return 0
        if failures >= FAILURES_BEFORE_EXIT:
            return 1
        if events and deadline:
            deadline = time.time() + arguments.timeout_minutes * 60
        time.sleep(POLL_SECONDS)


if __name__ == '__main__':
    sys.exit(main())
