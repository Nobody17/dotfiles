#!/usr/bin/env python3
"""Run a heavy job (tests, builds) in one of the run's heavy-job slots, and mark it for review when it runs long.

Usage:
  heavy-job.py --run <run> [--label <text>] [--slots N] [--review-after-minutes M] [--lock <path>]
               [--cleanup <shell command>] [--kill-after-seconds S] -- <command> [argument ...]
  heavy-job.py --run <run> --list                      the running jobs, for a review
  heavy-job.py --run <run> --extend <job> --minutes M  set the next review time to M minutes from now
  heavy-job.py --run <run> --stop <job> [--reason <text>]
                                                       stop the job, run its cleanup; the job exits 124
  heavy-job.py --run <run> --release <job>             after a failed cleanup: free the slot, end the job

Defaults come from ledger.heavy_jobs in <run>/ledger.json; an option overrides its key:
  slots                 number of jobs of the run that can run at the same time (default 1)
  review_after_minutes  run time after which the job needs a review, slot waiting excluded (required)
  lock                  slot lock file (default <run>/heavy-job.lock); slot k > 0 uses <lock>.<k>
  stop_cleanup          shell command, run in the job's directory after --stop, that stops what the
                        stopped client leaves behind (for example a process inside a container)
  memory_probe          shell command that prints the available memory of the pool in MB as its first
                        word (optional); the job samples it before the start and every
                        memory_probe_seconds (default 15)

The slots are flock(2) locks, so `lockf -k <lock> <command>` on macOS shares slot 0.
The script never stops a job by itself. At the review time it writes a line to stderr and marks
the job record as overdue; watch-run.py reports it, and a reviewer decides with --extend or --stop.
<run>/heavy-jobs/<job>.json records the job, <job>.log keeps its output; <job> is the wrapper's pid.
Each ended job adds one JSON line to <run>/heavy-jobs/history.jsonl: label, cwd, slot, start, seconds waited
for the slot, run seconds, exit code and, with memory_probe, the available MB before the start, the
lowest available MB, and their difference as the job's peak. Size slots and review time from this file.
The command runs in its own process group; the job holds its slot until the whole group has ended.
--stop sends SIGTERM to the group, SIGKILL after --kill-after-seconds (default 30), runs stop_cleanup,
and the job exits 124. A SIGTERM, SIGINT, or SIGHUP to this script stops the job the same way
(exit 128 + N). When stop_cleanup fails, the job keeps its slot until --stop (cleanup again) or --release.
The slot count is read again while a job waits, so a lowered ledger value applies to waiting jobs.
Other exit codes: the command's own exit code (128 + N after signal N); 125 for a wrong call or
configuration; 127 when the command does not exist.
Messages of this script go to stderr and start with "heavy-job:".
"""
import argparse
import datetime
import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

STOPPED_EXIT = 124
USAGE_EXIT = 125
NOT_FOUND_EXIT = 127
POLL_SECONDS = 2
CLEANUP_LIMIT_SECONDS = 300
MEMORY_PROBE_LIMIT_SECONDS = 30
DEFAULT_MEMORY_PROBE_SECONDS = 15
OUTPUT_DRAIN_SECONDS = 5


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--run', required=True, type=Path, help='run directory that holds ledger.json')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--list', action='store_true', help='print the running jobs')
    action.add_argument('--extend', metavar='JOB', help='set the next review time of JOB')
    action.add_argument('--stop', metavar='JOB', help='stop JOB and run its cleanup')
    action.add_argument('--release', metavar='JOB', help='free the slot of JOB after a failed cleanup')
    parser.add_argument('--minutes', type=float, help='with --extend: minutes from now')
    parser.add_argument('--reason', default='reviewer decision', help='with --stop: text for the job owner')
    parser.add_argument('--label', help='short name of the job for messages and the job record')
    parser.add_argument('--slots', type=int)
    parser.add_argument('--review-after-minutes', type=float)
    parser.add_argument('--lock', type=Path)
    parser.add_argument('--cleanup', help='shell command to run in the job directory after --stop')
    parser.add_argument('--kill-after-seconds', type=float, default=30)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    arguments = parser.parse_args(argv)
    if arguments.command[:1] == ['--']:
        arguments.command = arguments.command[1:]
    controlling = arguments.list or arguments.extend or arguments.stop or arguments.release
    if controlling and arguments.command:
        parser.error('give a command or --list, --extend, --stop, --release, not both')
    if not controlling and not arguments.command:
        parser.error('give the command after --')
    if arguments.extend and not (arguments.minutes and arguments.minutes > 0):
        parser.error('--extend needs --minutes with a value above 0')
    return arguments


def say(text):
    """Write a message to stderr. A closed or full stderr never stops the job management."""
    try:
        print(f'heavy-job: {text}', file=sys.stderr, flush=True)
    except OSError:
        pass


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def ledger_policy(run_directory):
    ledger_path = run_directory / 'ledger.json'
    if not ledger_path.exists():
        return {}
    return json.loads(ledger_path.read_text()).get('heavy_jobs') or {}


def job_settings(arguments, policy, run_directory):
    """Merge the command-line options over the ledger policy. Returns (settings, error)."""
    slots = arguments.slots if arguments.slots is not None else policy.get('slots', 1)
    review_minutes = (arguments.review_after_minutes if arguments.review_after_minutes is not None
                      else policy.get('review_after_minutes'))
    lock = arguments.lock or Path(policy.get('lock') or run_directory / 'heavy-job.lock')
    cleanup = arguments.cleanup if arguments.cleanup is not None else policy.get('stop_cleanup')
    if not isinstance(slots, int) or slots < 1:
        return None, f'slots must be a whole number of 1 or more, not {slots!r}'
    if not isinstance(review_minutes, (int, float)) or review_minutes <= 0:
        return None, 'no review time: set ledger.heavy_jobs.review_after_minutes or --review-after-minutes'
    probe_seconds = policy.get('memory_probe_seconds', DEFAULT_MEMORY_PROBE_SECONDS)
    if not isinstance(probe_seconds, (int, float)) or probe_seconds <= 0:
        return None, f'memory_probe_seconds must be a number above 0, not {probe_seconds!r}'
    return {'slots': slots, 'review_seconds': review_minutes * 60, 'lock': lock, 'cleanup': cleanup,
            'memory_probe': policy.get('memory_probe'), 'memory_probe_seconds': probe_seconds}, None


def slot_lock_paths(lock, slots):
    return [lock if index == 0 else lock.with_name(f'{lock.name}.{index}') for index in range(slots)]


def try_lock(path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return descriptor
    except BlockingIOError:
        os.close(descriptor)
        return None


def existing_slot_files(lock):
    """The slot lock files that exist now, including slots above a lowered slot count."""
    suffixes = (path.name[len(lock.name) + 1:] for path in lock.parent.glob(f'{lock.name}.*'))
    return [lock] + [lock.with_name(f'{lock.name}.{suffix}') for suffix in suffixes if suffix.isdigit()]


def try_take_slot(lock_paths):
    """Take a free slot of lock_paths when fewer than len(lock_paths) slot files are held, counting
    the slot files above the current count too. Returns (slot index, descriptor) or None."""
    probed = {}
    for path in sorted(set(lock_paths) | set(existing_slot_files(lock_paths[0])), key=str):
        probed[path] = try_lock(path)
    busy = sum(1 for descriptor in probed.values() if descriptor is None)
    chosen = None
    if busy < len(lock_paths):
        chosen = next(((index, probed[path]) for index, path in enumerate(lock_paths) if probed[path] is not None), None)
    for descriptor in probed.values():
        if descriptor is not None and (chosen is None or descriptor != chosen[1]):
            os.close(descriptor)
    return chosen


def acquire_slot(current_lock_paths, label):
    """Block until one slot is free. Reads the slot count again before each round, and counts jobs in slots
    above a lowered ledger.heavy_jobs.slots as busy. Returns (slot index, slot count, descriptor)."""
    announced = False
    while True:
        lock_paths = current_lock_paths()
        lock_paths[0].parent.mkdir(parents=True, exist_ok=True)
        taken = try_take_slot(lock_paths)
        if taken is not None:
            return taken[0], len(lock_paths), taken[1]
        if not announced:
            say(f'waiting for a free slot ({len(lock_paths)} busy): {label}')
            announced = True
        time.sleep(POLL_SECONDS)


def group_alive(process_group):
    try:
        os.killpg(process_group, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def signal_group(process_group, signal_number):
    try:
        os.killpg(process_group, signal_number)
    except ProcessLookupError:
        pass


def stop_group(process, kill_after_seconds):
    """SIGTERM to the whole group, SIGKILL to what is left after kill_after_seconds."""
    signal_group(process.pid, signal.SIGTERM)
    give_up_at = time.time() + kill_after_seconds
    while time.time() < give_up_at:
        process.poll()
        if not group_alive(process.pid):
            return
        time.sleep(0.2)
    signal_group(process.pid, signal.SIGKILL)
    process.wait()


def run_cleanup(command):
    """Run the stop cleanup. Returns True when it ended with exit 0."""
    say(f'stop cleanup: {command}')
    try:
        result = subprocess.run(command, shell=True, timeout=CLEANUP_LIMIT_SECONDS)
    except subprocess.TimeoutExpired:
        say(f'stop cleanup did not end within {CLEANUP_LIMIT_SECONDS} s')
        return False
    say(f'stop cleanup exit {result.returncode}')
    return result.returncode == 0


def shell_exit_code(return_code):
    return 128 - return_code if return_code < 0 else return_code


class OutputCopy:
    """Copy one output pipe of the job to the job log and, while it accepts output, to this script's stream."""

    def __init__(self, source, destination, log):
        self.last_output = time.time()
        self.thread = threading.Thread(target=self.copy, args=(source, destination, log), daemon=True)
        self.thread.start()

    def copy(self, source, destination, log):
        destination_open = True
        log_open = True
        while chunk := os.read(source.fileno(), 65536):
            self.last_output = time.time()
            if log_open:
                try:
                    log.write(chunk)
                    log.flush()
                except OSError:
                    log_open = False  # for example a full disk; keep reading so the job never blocks
            if destination_open:
                try:
                    destination.write(chunk)
                    destination.flush()
                except OSError:
                    destination_open = False  # the reader is gone; keep reading so the job never blocks


def probe_available_megabytes(command):
    """Run the memory probe. Returns the first word of its output as a number, or None."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=MEMORY_PROBE_LIMIT_SECONDS)
        return float(result.stdout.split()[0]) if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, IndexError, ValueError, OSError):
        return None


class MemorySamples:
    """Sample the available memory of the pool: once before the job starts, then in a thread until stop()."""

    def __init__(self, command, interval_seconds):
        self.command = command
        self.before_start = probe_available_megabytes(command)
        self.lowest = self.before_start
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.sample, args=(interval_seconds,), daemon=True)
        self.thread.start()

    def sample(self, interval_seconds):
        while not self.stopped.wait(interval_seconds):
            available = probe_available_megabytes(self.command)
            if available is not None and (self.lowest is None or available < self.lowest):
                self.lowest = available

    def stop(self):
        self.stopped.set()

    def summary(self):
        if self.before_start is None or self.lowest is None:
            return {}
        return {'memory_available_before_mb': self.before_start, 'memory_available_lowest_mb': self.lowest,
                'memory_peak_mb': self.before_start - self.lowest}


def request_paths(jobs_directory, job):
    return sorted(jobs_directory.glob(f'{job}.request-*.json'))


def take_requests(jobs_directory, job):
    """Take every pending request of the job, oldest first. A rename takes a request atomically."""
    requests = []
    for path in request_paths(jobs_directory, job):
        taken = path.with_name(path.name + '.taken')
        try:
            path.rename(taken)
            requests.append(json.loads(taken.read_text()))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        taken.unlink(missing_ok=True)
    return requests


def send_request(jobs_directory, job, request):
    write_json(jobs_directory / f'{job}.request-{time.time_ns()}.json', request)


class JobRunner:
    """One heavy job from slot to exit. States: running, group running (the command ended, processes of its
    group still run), cleanup failed (stopped, cleanup failed; the slot stays held until --release)."""

    def __init__(self, arguments, settings, run_directory, slot, slot_count, waited_seconds=0.0):
        self.arguments, self.settings = arguments, settings
        self.waited_seconds = waited_seconds
        self.memory = None
        self.label = arguments.label or ' '.join(arguments.command)[:80]
        self.jobs_directory = run_directory / 'heavy-jobs'
        self.job = str(os.getpid())
        self.record_path = self.jobs_directory / f'{self.job}.json'
        self.log_path = self.jobs_directory / f'{self.job}.log'
        self.slot, self.slot_count = slot, slot_count
        self.state = 'running'
        self.exit_code = None
        self.received_signal = None
        self.overdue_announced = False
        self.group_announced = False
        self.leader_exit_code = None
        self.pending_exit_code = None
        self.record_error_announced = False
        self.cleanup_attempts = 0

    def start(self):
        self.jobs_directory.mkdir(parents=True, exist_ok=True)
        for path in request_paths(self.jobs_directory, self.job):
            path.unlink(missing_ok=True)
        self.started = now_utc()
        self.review_at = self.started + datetime.timedelta(seconds=self.settings['review_seconds'])
        say(f'job {self.job}, slot {self.slot + 1}/{self.slot_count}; review after '
            f'{self.settings["review_seconds"] / 60:g} min; log {self.log_path}: {self.label}')
        self.log = self.log_path.open('wb')
        for signal_number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(signal_number, self.note_signal)
        if self.settings.get('memory_probe'):
            self.memory = MemorySamples(self.settings['memory_probe'], self.settings['memory_probe_seconds'])
        self.process = subprocess.Popen(self.arguments.command, start_new_session=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.copies = [OutputCopy(self.process.stdout, sys.stdout.buffer, self.log),
                       OutputCopy(self.process.stderr, sys.stderr.buffer, self.log)]

    def note_signal(self, signal_number, _frame):
        self.received_signal = signal_number

    def write_record(self):
        """Write the job record. A write error (for example a full disk) keeps the job and its slot."""
        try:
            self.write_record_file()
        except OSError as error:
            if not self.record_error_announced:
                say(f'cannot write the job record, the job continues: {error}')
                self.record_error_announced = True

    def write_record_file(self):
        last_output = max(copy.last_output for copy in self.copies)
        write_json(self.record_path, {
            'job': self.job, 'label': self.label, 'command': self.arguments.command, 'cwd': os.getcwd(),
            'slot': self.slot, 'pid': os.getpid(), 'process_group': self.process.pid, 'state': self.state,
            'cleanup_attempts': self.cleanup_attempts,
            'started': self.started.isoformat(), 'review_at': self.review_at.isoformat(),
            'overdue': now_utc() > self.review_at,
            'last_output': datetime.datetime.fromtimestamp(last_output, datetime.timezone.utc).isoformat(),
            'log': str(self.log_path),
        })

    def stop(self, reason, exit_code):
        say(f'stop {reason}; stopping the job: {self.label}')
        stop_group(self.process, self.arguments.kill_after_seconds)
        cleaned = True
        if self.settings['cleanup']:
            self.cleanup_attempts += 1
            cleaned = run_cleanup(self.settings['cleanup'])
        if cleaned:
            say(f'exit {exit_code} (stopped): {self.label}')
            self.exit_code = exit_code
        else:
            say(f'cleanup failed; the slot stays held until --stop (cleanup again) or --release: {self.label}')
            self.state, self.pending_exit_code = 'cleanup failed', exit_code

    def handle_requests(self):
        for request in take_requests(self.jobs_directory, self.job):
            action = request.get('action')
            if action == 'stop':
                if self.state == 'cleanup failed':
                    self.state = 'running'
                self.stop(f'requested: {request.get("reason", "no reason given")}', STOPPED_EXIT)
            elif action == 'release' and self.state == 'cleanup failed':
                say(f'slot released by request; exit {self.pending_exit_code}: {self.label}')
                self.exit_code = self.pending_exit_code
            elif action == 'extend' and self.state != 'cleanup failed':
                self.review_at = now_utc() + datetime.timedelta(minutes=request['minutes'])
                self.overdue_announced = False
                say(f'review time moved to {self.review_at:%H:%M:%S} UTC: {self.label}')
            else:
                say(f'request {action!r} does not apply in state {self.state!r}: {self.label}')
            if self.exit_code is not None:
                return

    def observe_command(self):
        if self.state == 'running':
            try:
                self.leader_exit_code = shell_exit_code(self.process.wait(timeout=POLL_SECONDS))
            except subprocess.TimeoutExpired:
                return
            self.state = 'group running'
        else:
            time.sleep(POLL_SECONDS)
        if self.state == 'group running':
            if not group_alive(self.process.pid):
                self.exit_code = self.leader_exit_code
            elif not self.group_announced:
                say(f'the command ended, but processes of its group still run; the slot stays held: {self.label}')
                self.group_announced = True

    def announce_review(self):
        if self.state != 'cleanup failed' and now_utc() > self.review_at and not self.overdue_announced:
            minutes = (now_utc() - self.started).total_seconds() / 60
            say(f'running {minutes:.0f} min; needs a review, the job continues: {self.label}')
            self.overdue_announced = True

    def run(self):
        while self.exit_code is None:
            self.write_record()
            self.observe_command()
            if self.received_signal is not None and self.state != 'cleanup failed':
                number, self.received_signal = self.received_signal, None
                self.exit_code = None  # the command can end in the same round; its cleanup still runs
                self.stop(f'by signal {signal.Signals(number).name} to the wrapper', 128 + number)
                continue
            if self.exit_code is not None:
                break
            self.handle_requests()
            if self.exit_code is None:
                self.announce_review()
        for copy in self.copies:
            copy.thread.join(OUTPUT_DRAIN_SECONDS)
        return self.exit_code

    def write_history(self):
        """Add the ended job to history.jsonl. A write error never changes the job's result."""
        if not hasattr(self, 'started'):
            return
        if self.memory:
            self.memory.stop()
        entry = {'job': self.job, 'label': self.label, 'cwd': os.getcwd(), 'slot': self.slot,
                 'started': self.started.isoformat(), 'waited_seconds': round(self.waited_seconds),
                 'run_seconds': round((now_utc() - self.started).total_seconds()), 'exit': self.exit_code,
                 **(self.memory.summary() if self.memory else {})}
        try:
            with (self.jobs_directory / 'history.jsonl').open('a') as history:
                history.write(json.dumps(entry) + '\n')
        except OSError as error:
            say(f'cannot write the job history: {error}')

    def close(self):
        self.write_history()
        self.record_path.unlink(missing_ok=True)
        for path in request_paths(self.jobs_directory, self.job):
            path.unlink(missing_ok=True)
        if hasattr(self, 'log'):
            self.log.close()


def run_job(arguments, settings, run_directory):
    def current_lock_paths():
        slots = settings['slots']
        if arguments.slots is None:
            try:
                slots = ledger_policy(run_directory).get('slots', slots)
            except (OSError, json.JSONDecodeError):
                pass
        return slot_lock_paths(settings['lock'], slots if isinstance(slots, int) and slots >= 1 else 1)

    label = arguments.label or ' '.join(arguments.command)[:80]
    wait_started = time.time()
    slot, slot_count, descriptor = acquire_slot(current_lock_paths, label)
    runner = JobRunner(arguments, settings, run_directory, slot, slot_count, time.time() - wait_started)
    try:
        runner.start()
        return runner.run()
    finally:
        runner.close()
        os.close(descriptor)


def running_records(jobs_directory):
    records = []
    for path in sorted(jobs_directory.glob('*.json')):
        if '.request-' in path.name:
            continue
        try:
            records.append(json.loads(path.read_text()))
        except (OSError, json.JSONDecodeError):
            continue
    return records


def group_processes(process_group):
    """Return 'pid stat elapsed rss-kB command' lines of the processes in one process group."""
    result = subprocess.run(['ps', '-axo', 'pgid=,pid=,stat=,etime=,rss=,command='], capture_output=True, text=True)
    lines = []
    for line in result.stdout.splitlines():
        fields = line.split(None, 1)
        if len(fields) == 2 and fields[0] == str(process_group):
            lines.append(fields[1][:160])
    return lines


def describe_job(record, now):
    started = datetime.datetime.fromisoformat(record['started'])
    last_output = datetime.datetime.fromisoformat(record['last_output'])
    review_at = datetime.datetime.fromisoformat(record['review_at'])
    review = (f'review due since {(now - review_at).total_seconds() / 60:.0f} min' if now > review_at
              else f'review in {(review_at - now).total_seconds() / 60:.0f} min')
    wrapper = '' if process_alive(record.get('pid', 0)) else ', WRAPPER ENDED: nothing watches this job'
    return (f'job {record["job"]} {record["label"]}: {record.get("state", "running")}{wrapper}\n'
            f'  running {(now - started).total_seconds() / 60:.0f} min, {review}, '
            f'last output {(now - last_output).total_seconds() / 60:.0f} min ago\n'
            f'  cwd {record["cwd"]}\n  log {record["log"]}\n  command {" ".join(record["command"])}')


def list_jobs(run_directory):
    records = running_records(run_directory / 'heavy-jobs')
    if not records:
        print('no running heavy jobs')
    for record in records:
        print(describe_job(record, now_utc()))
        print('  processes (pid stat elapsed rss-kB command; stat Z = ended child that nobody collected):')
        for line in group_processes(record['process_group']):
            print(f'    {line}')
    return 0


def process_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def request_action(run_directory, job, request):
    jobs_directory = run_directory / 'heavy-jobs'
    record_path = jobs_directory / f'{job}.json'
    if not record_path.exists():
        say(f'no running job {job}; see --list')
        return USAGE_EXIT
    if not process_alive(json.loads(record_path.read_text()).get('pid', 0)):
        say(f'the wrapper of job {job} has ended; act on its process group yourself, then delete {record_path}')
        return USAGE_EXIT
    send_request(jobs_directory, job, request)
    say(f'request sent to job {job}; it acts within {POLL_SECONDS} s')
    return 0


def main(argv):
    arguments = parse_arguments(argv)
    run_directory = arguments.run.resolve()
    if arguments.list:
        return list_jobs(run_directory)
    if arguments.extend:
        return request_action(run_directory, arguments.extend, {'action': 'extend', 'minutes': arguments.minutes})
    if arguments.stop:
        return request_action(run_directory, arguments.stop, {'action': 'stop', 'reason': arguments.reason})
    if arguments.release:
        return request_action(run_directory, arguments.release, {'action': 'release'})
    try:
        policy = ledger_policy(run_directory)
    except (OSError, json.JSONDecodeError) as error:
        say(f'cannot read the ledger: {error}')
        return USAGE_EXIT
    settings, error = job_settings(arguments, policy, run_directory)
    if error:
        say(error)
        return USAGE_EXIT
    try:
        return run_job(arguments, settings, run_directory)
    except FileNotFoundError as error:
        say(f'cannot start the command: {error}')
        return NOT_FOUND_EXIT


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
