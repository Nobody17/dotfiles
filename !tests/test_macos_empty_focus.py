"""Empty workspaces must not trap directional keyboard or mouse focus."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(os.environ.get('FOCUS_HELPER', str(Path(__file__).resolve().parents[1] / 'aerospace/.config/aerospace/focus-pane-or-window.sh')))


class EmptyWorkspaceFocusTests(unittest.TestCase):
    def run_helper(self, *extra, unavailable=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / 'calls'
            command = root / 'aerospace'
            command.write_text('''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['CALL_LOG'], 'a') as f:
    f.write(json.dumps(sys.argv[1:]) + '\\n')
if os.environ['UNAVAILABLE'] == '1':
    sys.exit(1)
if sys.argv[1] == 'list-windows':
    sys.exit(1)  # AeroSpace reports no focused window with a nonzero status.
if sys.argv[1] == 'list-workspaces':
    print('11')
if sys.argv[1:] == ['move-mouse', 'window-lazy-center']:
    sys.exit(2)  # Destination can also be an empty workspace.
''')
            command.chmod(0o755)
            env = dict(os.environ, PATH=f'{root}:' + os.environ['PATH'], CALL_LOG=str(log),
                       UNAVAILABLE='1' if unavailable else '0')
            result = subprocess.run(['sh', str(HELPER), 'right', *extra], env=env,
                                    capture_output=True, text=True, timeout=5)
            return result, [json.loads(line) for line in log.read_text().splitlines()]

    def test_empty_workspace_can_navigate_and_move_pointer_to_empty_destination(self):
        result, calls = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(['focus', '--boundaries', 'all-monitors-outer-frame',
                       '--boundaries-action', 'wrap-around-all-monitors', 'right'], calls)
        self.assertIn(['move-mouse', 'monitor-lazy-center'], calls)

    def test_late_pane_callback_does_not_navigate_without_originating_window(self):
        _, calls = self.run_helper('--from-herdr')
        self.assertFalse(any(c[0] == 'focus' for c in calls))

    def test_unavailable_aerospace_is_not_treated_as_an_empty_workspace(self):
        result, calls = self.run_helper(unavailable=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] == 'focus' for c in calls))


if __name__ == '__main__':
    unittest.main()
