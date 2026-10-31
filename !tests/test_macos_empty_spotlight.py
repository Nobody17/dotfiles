"""Live regression: EMPTY_SPOTLIGHT_WORKSPACE=10 python3 -m unittest discover
-s '!tests' -p test_macos_empty_spotlight.py

Briefly changes workspace and opens Spotlight; restores the original workspace.
"""
import os
from pathlib import Path
import subprocess
import time
import unittest


def aerospace(*arguments):
    return subprocess.check_output(['aerospace', *arguments], text=True).strip()


def javascript(source):
    return subprocess.check_output(['osascript', '-l', 'JavaScript', '-e', source],
                                   text=True).strip()


def spotlight_open():
    return javascript("const process = Application('System Events').processes.byName('Spotlight');"
                      "process.exists() && process.windows.length > 0") == 'true'


@unittest.skipUnless(os.environ.get('EMPTY_SPOTLIGHT_WORKSPACE'), 'requires an empty workspace')
class EmptySpotlightTests(unittest.TestCase):
    def wait_for(self, condition):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.05)
        self.fail('Expected desktop state did not appear')

    def test_spotlight_opens_on_empty_workspace(self):
        self.assertFalse(spotlight_open(), 'Close Spotlight before this live test')
        original = aerospace('list-workspaces', '--focused')
        self.addCleanup(aerospace, 'workspace', original)
        self.addCleanup(self.close_spotlight)
        workspace = os.environ['EMPTY_SPOTLIGHT_WORKSPACE']
        self.assertEqual(aerospace('list-windows', '--workspace', workspace, '--count'), '0')
        aerospace('workspace', workspace)
        aerospace('move-mouse', 'monitor-lazy-center')
        self.wait_for(lambda: javascript(
            'ObjC.import("AppKit"); '
            '$.NSWorkspace.sharedWorkspace.frontmostApplication.bundleIdentifier.js'
        ) in ('com.apple.dock', 'com.apple.systemuiserver'))
        helper = Path(__file__).resolve().parents[1] / 'aerospace/.config/aerospace/open-spotlight.js'
        subprocess.run(['osascript', '-l', 'JavaScript', str(helper)], check=True, timeout=10)
        self.wait_for(spotlight_open)
        self.assertEqual(aerospace('list-workspaces', '--focused'), workspace)

    def close_spotlight(self):
        if spotlight_open():
            javascript("Application('System Events').keyCode(53)")
            self.wait_for(lambda: not spotlight_open())


if __name__ == '__main__':
    unittest.main()
