"""Exercise the macOS helper with two clients sharing one Herdr session."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'aerospace/.config/aerospace/focus-pane-or-window.sh'


class MacFocusTests(unittest.TestCase):
    def run_focus(self, result, *args, active_pane='w1:p1', window_changed=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / 'calls'
            stub = '''#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as f:
    f.write(json.dumps([name, *args]) + '\\n')
if name == 'mise':
    print(pathlib.Path(sys.argv[0]).with_name('herdr'))
elif name == 'ps':
    print('10 1 ghostty\\n20 10 herdr\\n30 1 ghostty\\n40 30 herdr')
elif name == 'aerospace' and args[0] == 'list-windows':
    if args[-1] == '%{app-pid}':
        print('10')
    elif '%{app-pid}' in args[-1]:
        print('10|test-host: project')
    else:
        previous = pathlib.Path(os.environ['CALL_LOG']).read_text().count('%{window-id}')
        print('200' if os.environ['WINDOW_CHANGED'] == '1' and previous > 1 else '100')
elif name == 'herdr':
    if '--pane' not in args:
        print(json.dumps({'result': {'focus': {'changed': True, 'source_pane_id': 'w1:p9'}}}))
    else:
        print(os.environ['FOCUS_RESULT'])
'''
            for name in ('aerospace', 'herdr', 'mise', 'ps', 'osascript'):
                path = root / name
                path.write_text(stub)
                path.chmod(0o755)
            env = dict(os.environ, PATH=f'{root}:' + os.environ['PATH'],
                       CALL_LOG=str(log), FOCUS_RESULT=json.dumps(result),
                       HERDR_ACTIVE_PANE_ID=active_pane,
                       HERDR_BIN_PATH=str(root / 'herdr'),
                       WINDOW_CHANGED='1' if window_changed else '0')
            completed = subprocess.run(['sh', str(HELPER), *args], env=env,
                                       capture_output=True, text=True)
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return completed, calls

    def test_client_context_targets_selected_pane_not_other_window(self):
        completed, calls = self.run_focus({'result': {'focus': {'changed': True}}}, 'left', '--from-herdr')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        focus = [c for c in calls if c[0] == 'herdr']
        self.assertEqual(len(focus), 1)
        self.assertIn('--pane', focus[0])
        self.assertEqual(focus[0][focus[0].index('--pane') + 1], 'w1:p1')
        self.assertFalse(any(c[:2] == ['aerospace', 'focus'] for c in calls))

    def test_only_confirmed_edge_switches_windows(self):
        for reason, expected in [('no_neighbor', True), ('unavailable', False)]:
            with self.subTest(reason=reason):
                _, calls = self.run_focus({'result': {'focus': {'changed': False, 'reason': reason}}},
                                         'right', '--from-herdr')
                self.assertEqual(any(c[:2] == ['aerospace', 'focus'] for c in calls), expected)

    def test_api_error_does_not_switch_windows(self):
        _, calls = self.run_focus({'error': {'code': 'protocol_mismatch'}}, 'down', '--from-herdr')
        self.assertFalse(any(c[:2] == ['aerospace', 'focus'] for c in calls))

    def test_missing_client_context_never_uses_global_focus(self):
        _, calls = self.run_focus({}, 'up', '--from-herdr', active_pane='')
        self.assertFalse(any(c[0] == 'herdr' or c[:2] == ['aerospace', 'focus'] for c in calls))

    def test_window_switch_is_cancelled_if_user_changed_windows(self):
        _, calls = self.run_focus({'result': {'focus': {'changed': False, 'reason': 'no_neighbor'}}},
                                 'right', '--from-herdr', window_changed=True)
        self.assertFalse(any(c[:2] == ['aerospace', 'focus'] for c in calls))

    def test_window_shortcut_routes_through_client_without_global_api_focus(self):
        for direction in ('left', 'down', 'up', 'right'):
            with self.subTest(direction=direction):
                _, calls = self.run_focus({}, direction)
                self.assertIn(['osascript', '-l', 'JavaScript', str(HELPER.with_name('send-herdr-focus.js')), '10', direction], calls)
                self.assertFalse(any(c[0] == 'herdr' and 'focus' in c for c in calls))


if __name__ == '__main__':
    unittest.main()
