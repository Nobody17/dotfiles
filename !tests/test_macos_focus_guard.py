"""Opt-in read-only check of the helper's real macOS focus guard.

Focus the second instance of a duplicated terminal app, then run:
MACOS_FOCUS_CHECK=1 python3 -m unittest discover -s '!tests' -p test_macos_focus_guard.py
No keys are sent and no windows are moved by this test.
"""
import os
from pathlib import Path
import subprocess
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'aerospace/.config/aerospace/focus-pane-or-window.sh'


@unittest.skipUnless(os.environ.get('MACOS_FOCUS_CHECK') == '1', 'requires a focused macOS test window')
class MacFocusGuardTests(unittest.TestCase):
    def test_focused_process_is_not_confused_with_another_instance_of_same_app(self):
        pid = subprocess.check_output(['aerospace', 'list-windows', '--focused',
                                       '--format', '%{app-pid}'], text=True).strip()
        script = HELPER.with_name('send-herdr-focus.js').read_text()
        # Run the production PID guard and descriptor construction without input.
        send = 'const reply = event.sendEventWithOptionsTimeoutError(3, 3, error);'
        self.assertEqual(script.count(send), 1)
        script = script.replace(send, 'return String(pid);')
        result = subprocess.run(['osascript', '-l', 'JavaScript', '-', pid, 'left'], input=script,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), pid)
