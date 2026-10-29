"""Read-only routing benchmark; never sends input or moves a real window.

Run after building/installing aerospace-send-herdr-focus:
    python3 '!tests/benchmark_macos_focus.py'

Optional first argument: an older focus-pane-or-window.sh for comparison.
Uses real CLI/runtime startup, fixture window/process discovery, and an invalid
target PID to stop before sending input. Excludes Herdr handling and redraw.
"""
import os
from pathlib import Path
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import time


helper = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[1] / 'aerospace/.config/aerospace/focus-pane-or-window.sh'
)
aerospace = shlex.quote(shutil.which('aerospace') or '/opt/homebrew/bin/aerospace')
mise = shlex.quote(shutil.which('mise') or '/opt/homebrew/bin/mise')

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    scripts = {
        # Keep actual CLI startup costs, but never contact the window manager.
        'aerospace': f'{aerospace} --help >/dev/null\n' + '''
case "$*" in
  *'%{app-bundle-id}'*) printf '100|2147483647|%s|test-host: project\\n' "$BENCH_APP";;
  *'%{app-pid}|%{window-title}'*) echo '2147483647|test-host: project';;
  *'%{app-pid}'*) echo 2147483647;;
  *'%{window-id}'*) echo 100;;
esac
''',
        'mise': f'{mise} which herdr >/dev/null\n' + 'printf "%s/herdr\\n" "${0%/*}"\n',
        # The benchmark must never inspect a running Herdr session.
        'herdr': 'exit 1\n',
        'ps': '''
[ "$BENCH_APP" = com.mitchellh.ghostty ] || exit 0
echo '2147483647 1 Ghostty'
echo '20 2147483647 herdr'
''',
    }
    for name, script in scripts.items():
        path = root / name
        path.write_text('#!/bin/sh\n' + script)
        path.chmod(0o755)

    for app in ('com.apple.Safari', 'com.mitchellh.ghostty'):
        env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'], BENCH_APP=app)
        samples = []
        for _ in range(6):
            start = time.perf_counter()
            result = subprocess.run(['sh', str(helper), 'left'], env=env,
                                    capture_output=True, text=True, timeout=5)
            # The Ghostty route must reach the real sender and stop at its PID
            # guard, rather than accidentally timing a broken/empty code path.
            if app == 'com.mitchellh.ghostty':
                assert result.returncode != 0 and 'Focused Ghostty process changed' in result.stderr, result
            else:
                assert result.returncode == 0, result.stderr
            samples.append((time.perf_counter() - start) * 1000)
        median = statistics.median(samples[1:])
        print(f'{app}: {median:.1f} ms warm median (first run {samples[0]:.1f} ms)')
        assert median < 50, f'Routing exceeds the 50 ms budget: {median:.1f} ms'
