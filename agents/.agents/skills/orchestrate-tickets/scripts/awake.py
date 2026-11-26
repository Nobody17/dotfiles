"""Keep the machine awake while a process runs, and measure the time the machine slept.

`caffeinate -i` (macOS) holds off the sleep by idle time only. A sleep that the user starts
(lid, menu) still occurs: all processes pause and continue afterwards. The wall clock counts
that time and the steady clock does not, so their difference is the time slept.
"""
import shutil
import subprocess
import time

NOTABLE_SLEEP_SECONDS = 60


def keep_awake(pid):
    """Hold off idle sleep until process `pid` ends. Returns the helper process, or None without caffeinate."""
    caffeinate = shutil.which('caffeinate')
    if caffeinate is None:
        return None
    return subprocess.Popen([caffeinate, '-i', '-w', str(pid)],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def slept_seconds(wall_before, wall_now, steady_before, steady_now):
    """Seconds the machine slept between two readings; 0 below NOTABLE_SLEEP_SECONDS."""
    slept = (wall_now - wall_before) - (steady_now - steady_before)
    return slept if slept >= NOTABLE_SLEEP_SECONDS else 0.0


class SleepMeter:
    """Reports the sleep since the last call of `take`."""

    def __init__(self, wall_clock=time.time, steady_clock=time.monotonic):
        self.wall_clock, self.steady_clock = wall_clock, steady_clock
        self.wall, self.steady = wall_clock(), steady_clock()

    def take(self):
        wall, steady = self.wall_clock(), self.steady_clock()
        slept = slept_seconds(self.wall, wall, self.steady, steady)
        self.wall, self.steady = wall, steady
        return slept
