"""Exercise the real tab helper with isolated AeroSpace and frame-provider doubles."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'aerospace/.config/aerospace/float-macos-tabs.sh'


class TabLayoutTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.state = self.root / 'windows.json'
        self.handled = self.root / 'aerospace-handled-windows'
        command = self.root / 'aerospace'
        command.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
path = Path(os.environ['WINDOW_FIXTURE'])
windows = json.loads(path.read_text())
args = sys.argv[1:]
if args[0] == 'list-windows':
    for window in windows:
        print(str(window['id']) + '|' + window['layout'])
elif args[0] == 'layout':
    if os.environ.get('FAIL_LAYOUT') == '1':
        sys.exit(1)
    for window in windows:
        if str(window['id']) == args[args.index('--window-id') + 1]:
            window['layout'] = args[1]
    path.write_text(json.dumps(windows))
else:
    sys.exit(2)
''')
        command.chmod(0o755)
        self.frames = self.root / '.local/bin/aerospace-window-frames'
        self.frames.parent.mkdir(parents=True)
        self.frames.write_text('''#!/usr/bin/env python3
import json, os
from pathlib import Path
for w in json.loads(Path(os.environ['WINDOW_FIXTURE']).read_text()):
    print(w['id'], w['pid'], 0, 38, 3834, 2021, w['visible'])
''')
        self.frames.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.root), TMPDIR=str(self.root),
                        PATH=str(self.root) + ':' + os.environ['PATH'],
                        WINDOW_FIXTURE=str(self.state))

    def window(self, identifier, layout='h_tiles', visible=1, pid=653):
        return dict(id=identifier, layout=layout, visible=visible, pid=pid)

    def run_helper(self, windows):
        self.state.write_text(json.dumps(windows))
        result = subprocess.run(['sh', str(HELPER)], env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(self.state.read_text())

    def group_tabs(self):
        self.handled.write_text('1\n')
        return self.run_helper([self.window(1), self.window(2, 'floating', 0)])

    def test_ordinary_tiles_do_not_rewrite_tab_ownership_for_each_window(self):
        moves = self.root / 'moves'
        move = self.root / 'mv'
        move.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >>"' + str(moves) +
                        '"\nexec /bin/mv "$@"\n')
        move.chmod(0o755)
        self.handled.write_text(''.join(f'{i}\n' for i in range(1, 21)))
        self.run_helper([self.window(i) for i in range(1, 21)])
        calls = moves.read_text().splitlines() if moves.exists() else []
        self.assertFalse(any('aerospace-tab-floated-windows' in call for call in calls))

    def test_two_visible_windows_with_equal_frames_keep_their_tiles(self):
        self.handled.write_text('1\n2\n')
        windows = self.run_helper([self.window(1), self.window(2)])
        self.assertEqual([w['layout'] for w in windows], ['h_tiles', 'h_tiles'])

    def test_last_tab_gets_tile_when_anchor_closes(self):
        windows = self.group_tabs()
        self.assertEqual([w['layout'] for w in windows], ['h_tiles', 'floating'])
        windows[1]['visible'] = 1
        survivor = self.run_helper(windows[1:])
        self.assertEqual(survivor[0]['layout'], 'tiling')

    def test_detached_tab_gets_own_tile(self):
        windows = self.group_tabs()
        windows[1]['visible'] = 1
        windows = self.run_helper(windows)
        self.assertEqual([w['layout'] for w in windows], ['h_tiles', 'tiling'])

    def test_switching_tabs_keeps_original_anchor(self):
        windows = self.group_tabs()
        windows[0]['visible'], windows[1]['visible'] = 0, 1
        windows = self.run_helper(windows)
        self.assertEqual([w['layout'] for w in windows], ['h_tiles', 'floating'])

    def test_user_float_is_preserved_after_automatic_restore(self):
        windows = self.group_tabs()[1:]
        windows[0]['visible'] = 1
        windows = self.run_helper(windows)
        self.assertEqual(windows[0]['layout'], 'tiling')
        windows[0]['layout'] = 'floating'
        self.assertEqual(self.run_helper(windows)[0]['layout'], 'floating')

    def test_existing_manual_float_is_preserved(self):
        self.handled.write_text('1\n')
        self.assertEqual(self.run_helper([self.window(1, 'floating')])[0]['layout'], 'floating')

    def test_helper_floats_tiled_tab_and_restores_it_after_anchor_closes(self):
        self.handled.write_text('1\n')
        windows = self.run_helper([self.window(1), self.window(2, visible=0)])
        self.assertEqual(windows[1]['layout'], 'floating')
        windows[1]['visible'] = 1
        self.assertEqual(self.run_helper(windows[1:])[0]['layout'], 'tiling')

    def test_hidden_workspace_does_not_lose_tab_ownership(self):
        windows = self.group_tabs()
        self.run_helper([self.window(3)])
        windows[1]['visible'] = 1
        self.assertEqual(self.run_helper(windows[1:])[0]['layout'], 'tiling')

    def test_first_run_preserves_existing_float(self):
        windows = self.run_helper([self.window(1, 'floating')])
        self.assertEqual(self.run_helper(windows)[0]['layout'], 'floating')

    def test_known_manual_float_is_not_claimed_as_a_tab(self):
        self.handled.write_text('1\n2\n')
        windows = self.run_helper([self.window(1), self.window(2, 'floating', 0)])
        windows[1]['visible'] = 1
        self.assertEqual(self.run_helper(windows[1:])[0]['layout'], 'floating')

    def test_missing_frames_does_not_restore_hidden_tab(self):
        windows = self.group_tabs()
        self.frames.unlink()
        self.assertEqual(self.run_helper(windows)[1]['layout'], 'floating')

    def test_failed_restore_is_retried(self):
        windows = self.group_tabs()[1:]
        windows[0]['visible'] = 1
        self.env['FAIL_LAYOUT'] = '1'
        self.assertEqual(self.run_helper(windows)[0]['layout'], 'floating')
        del self.env['FAIL_LAYOUT']
        self.assertEqual(self.run_helper(windows)[0]['layout'], 'tiling')

    def test_equal_frames_in_different_processes_are_not_tabs(self):
        self.handled.write_text('1\n2\n')
        windows = self.run_helper([self.window(1, visible=0), self.window(2, pid=999)])
        self.assertEqual([w['layout'] for w in windows], ['h_tiles', 'h_tiles'])


if __name__ == '__main__':
    unittest.main()
