"""Opt-in live check: window -> empty monitor must release native app focus.

EMPTY_FOCUS_WINDOW=140 EMPTY_FOCUS_MONITOR=2 python3 -m unittest discover \
    -s '!tests' -p test_macos_empty_native_focus.py

Uses the installed AeroSpace callback. Moves focus, sends no keys, and restores
the original workspace afterward. Choose a monitor with an empty workspace.
"""
import os
import subprocess
import time
import unittest


def aerospace(*args):
    return subprocess.check_output(['aerospace', *args], text=True).strip()


def active_app():
    return subprocess.check_output([
        'osascript', '-l', 'JavaScript', '-e',
        'ObjC.import("AppKit"); '
        '$.NSWorkspace.sharedWorkspace.frontmostApplication.bundleIdentifier.js',
    ], text=True).strip()


@unittest.skipUnless(os.environ.get('EMPTY_FOCUS_WINDOW') and
                     os.environ.get('EMPTY_FOCUS_MONITOR'), 'requires live monitor/window IDs')
class EmptyNativeFocusTests(unittest.TestCase):
    def test_empty_monitor_releases_app_and_window_can_regain_focus(self):
        original = aerospace('list-workspaces', '--focused')
        self.addCleanup(aerospace, 'workspace', original)
        window = os.environ['EMPTY_FOCUS_WINDOW']
        for _ in range(2):
            aerospace('focus', '--window-id', window)
            self.wait_for(lambda: aerospace('list-windows', '--focused',
                                           '--format', '%{window-id}') == window
                          and active_app() != 'com.apple.systemuiserver')
            aerospace('focus-monitor', os.environ['EMPTY_FOCUS_MONITOR'])
            self.assertEqual(aerospace('list-windows', '--workspace', 'focused', '--count'), '0',
                             'The test monitor must have an empty visible workspace')
            self.wait_for(lambda: active_app() == 'com.apple.systemuiserver')

    def wait_for(self, condition):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.05)
        self.fail('Native focus did not follow AeroSpace focus')
