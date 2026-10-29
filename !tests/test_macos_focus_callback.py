"""The real focus callback must bound work during rapid window navigation."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'aerospace/.config/aerospace/on-focus-changed.sh'


class FocusCallbackTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.helper = self.root / SOURCE.name
        shutil.copyfile(SOURCE, self.helper)
        self.log = self.root / 'calls'
        self.env = dict(os.environ, TMPDIR=str(self.root), CALL_LOG=str(self.log),
                        PATH=str(self.root) + ':' + os.environ['PATH'], WINDOW_COUNT='1')
        self.script('aerospace', '''
printf '%s\\n' "aerospace $*" >>"$CALL_LOG"
case "$*" in
  *--count*) [ "$WINDOW_COUNT" != error ] || exit 1; echo "$WINDOW_COUNT";;
  *) echo '42|1|h_tiles';;
esac
''')
        self.script('osascript', 'echo osascript >>"$CALL_LOG"\n')
        self.script('sleep', 'echo sleep >>"$CALL_LOG"\n')
        self.script('float-macos-tabs.sh', 'echo tabs >>"$CALL_LOG"\n')
        self.script('dwindle-autotiling.sh', 'echo dwindle >>"$CALL_LOG"\n')

    def script(self, name, body):
        path = self.root / name
        path.write_text('#!/bin/sh\n' + body)
        path.chmod(0o755)

    def run_callback(self):
        result = subprocess.run(['sh', str(self.helper)], env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.log.read_text().splitlines()

    def test_populated_workspace_skips_javascript(self):
        calls = self.run_callback()
        self.assertNotIn('osascript', calls)
        self.assertLess(calls.index('tabs'), calls.index('dwindle'))
        self.assertEqual((self.root / 'aerospace-last-focused-window').read_text(), '42|1\n')

    def test_empty_workspace_still_releases_native_focus(self):
        self.env['WINDOW_COUNT'] = '0'
        self.assertIn('osascript', self.run_callback())

    def test_server_error_does_not_release_native_focus(self):
        self.env['WINDOW_COUNT'] = 'error'
        self.assertNotIn('osascript', self.run_callback())

    def test_old_lock_with_live_owner_is_not_stolen(self):
        lock = self.root / 'aerospace-on-focus-changed.lock'
        lock.mkdir()
        (lock / 'pid').write_text(str(os.getpid()) + '\n')
        os.utime(lock, (0, 0))
        self.assertNotIn('tabs', self.run_callback())
        self.assertTrue(lock.exists())

    def test_abandoned_old_lock_can_be_recovered(self):
        lock = self.root / 'aerospace-on-focus-changed.lock'
        lock.mkdir()
        os.utime(lock, (0, 0))
        self.assertIn('tabs', self.run_callback())
        self.assertFalse(lock.exists())

    def test_burst_is_coalesced_without_polling_or_losing_final_pass(self):
        fifo = self.root / 'release'
        os.mkfifo(fifo)
        self.script('float-macos-tabs.sh', '''
echo tabs >>"$CALL_LOG"
if [ ! -e "$TMPDIR/ready" ]; then
    touch "$TMPDIR/ready"
    read -r release <"$TMPDIR/release"
fi
''')
        leader = subprocess.Popen(['sh', str(self.helper)], env=self.env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not (self.root / 'ready').exists():
                if time.monotonic() > deadline:
                    self.fail('Worker did not reach the barrier')
                time.sleep(0.01)
            for _ in range(8):
                self.run_callback()
            with fifo.open('w') as stream:
                stream.write('continue\n')
            _, error = leader.communicate(timeout=5)
            self.assertEqual(leader.returncode, 0, error)
            calls = self.log.read_text().splitlines()
            self.assertNotIn('sleep', calls)
            self.assertEqual(calls.count('tabs'), 2)
            self.assertEqual(calls.count('dwindle'), 2)
            self.assertFalse((self.root / 'aerospace-on-focus-changed.lock').exists())
        finally:
            if leader.poll() is None:
                leader.kill()
                leader.communicate()


if __name__ == '__main__':
    unittest.main()
