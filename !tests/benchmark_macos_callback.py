"""Measure callback CPU and elapsed time without changing the desktop.

    python3 '!tests/benchmark_macos_callback.py'

Optional --source points to an older .config/aerospace directory for comparison.
Real shell/JXA/file operations; fixture AeroSpace responses and window frames.
This measures callback overhead, excluding window-manager IPC and rendering.
"""
import argparse
import os
from pathlib import Path
import resource
import shlex
import shutil
import statistics
import subprocess
import tempfile
import time


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=(
    Path(__file__).resolve().parents[1] / 'aerospace/.config/aerospace'))
parser.add_argument('--windows', type=int, default=20)
args = parser.parse_args()
if args.windows < 1:
    parser.error('--windows must be positive')

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / '.local/bin').mkdir(parents=True)
    log = root / 'calls'

    def script(name, body):
        path = root / name
        path.write_text('#!/bin/sh\n' + body)
        path.chmod(0o755)

    script('aerospace', '''
printf '%s\\n' "aerospace $*" >>"$CALL_LOG"
case "$*" in
  *--count*) echo "$WINDOW_COUNT";;
  *'%{window-id}|%{workspace}|%{window-layout}'*) echo '1|1|h_tiles';;
  *'%{window-parent-container-layout}'*) echo '1|h_tiles|h_tiles|false';;
  *'%{window-id}|%{window-layout}'*)
    i=1; while [ "$i" -le "$WINDOW_COUNT" ]; do echo "$i|h_tiles"; i=$((i+1)); done;;
  *'%{window-id}'*)
    i=1; while [ "$i" -le "$WINDOW_COUNT" ]; do echo "$i"; i=$((i+1)); done;;
esac
''')
    script('.local/bin/aerospace-window-frames', 'exit 0\n')
    for name in ('aerospace-handled-windows', 'aerospace-dwindle-known-windows'):
        (root / name).write_text(''.join(f'{i}\n' for i in range(1, args.windows + 1)))
    for name in ('sed', 'mv', 'sort', 'stat', 'date', 'sleep', 'osascript'):
        binary = shutil.which(name)
        if not binary:
            parser.error(f'{name} is required (run this benchmark on macOS)')
        script(name, f'echo {name} >>"$CALL_LOG"\nexec {shlex.quote(binary)} "$@"\n')

    env = dict(os.environ, HOME=str(root), TMPDIR=str(root), CALL_LOG=str(log),
               WINDOW_COUNT=str(args.windows), PATH=str(root) + ':' + os.environ['PATH'])
    print(f'{args.windows} existing windows; medians of 3 runs:')
    for count in (1, 8):
        elapsed, cpu, commands = [], [], []
        for _ in range(3):
            log.write_text('')
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            started = time.perf_counter()
            processes = [subprocess.Popen(['sh', str(args.source / 'on-focus-changed.sh')],
                                          env=env, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.PIPE) for _ in range(count)]
            try:
                for process in processes:
                    _, error = process.communicate(timeout=15)
                    assert process.returncode == 0, error.decode()
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()
            elapsed.append((time.perf_counter() - started) * 1000)
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu.append((after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime) * 1000)
            commands.append(len(log.read_text().splitlines()))
        print(f'{count} callback(s): {statistics.median(elapsed):.1f} ms elapsed, '
              f'{statistics.median(cpu):.1f} ms CPU, '
              f'{statistics.median(commands):g} tracked commands')
