"""Run with python3 -m unittest discover -s '!tests' -p 'test_herdr_focus.py'."""

import importlib.machinery
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

HELPER = Path(__file__).resolve().parents[1] / "hypr/.local/bin/herdr-or-hyprland-focus"
sys.dont_write_bytecode = True
loader = importlib.machinery.SourceFileLoader("focus", str(HELPER))
spec = importlib.util.spec_from_loader(loader.name, loader)
focus = importlib.util.module_from_spec(spec)
loader.exec_module(focus)


class FocusTests(unittest.TestCase):
    def test_named_session_overrides_inherited_socket(self):
        self.assertEqual(focus.session_socket(["herdr", "--session", "work"], {
            "HERDR_CONFIG_PATH": "/config/herdr/config.toml",
            "HERDR_SOCKET_PATH": "/wrong.sock",
        }), "/config/herdr/sessions/work/herdr.sock")

    def test_session_attach_and_environment(self):
        env = {"XDG_CONFIG_HOME": "/config", "HERDR_SESSION": "personal"}
        self.assertEqual(focus.session_socket(["herdr"], env),
                         "/config/herdr/sessions/personal/herdr.sock")
        self.assertEqual(focus.session_socket(["herdr", "session", "attach", "work"], env),
                         "/config/herdr/sessions/work/herdr.sock")

    def test_routes_by_process_not_renamed_title_or_other_monitor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "environ").write_bytes(b"HERDR_SOCKET_PATH=/work.sock\0")
            stat = ["S", "10", "20", "20", "1", "20"]
            procs = {20: (10, ["herdr"], path, stat),
                     10: (1, ["ghostty"], path, stat)}
            active = {"pid": 10, "title": "My custom window", "monitor": 1}
            self.assertEqual(focus.find_socket(active, [active, {"pid": 99}], procs),
                             "/work.sock")
            self.assertIsNone(focus.find_socket({"pid": 99}, [active, {"pid": 99}], procs))
            self.assertIsNone(focus.find_socket(active, [active, active], procs))

    def test_real_socket_protocol_for_neighbor_and_border(self):
        for changed in (True, False):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                path = str(Path(directory) / "herdr.sock")
                with socket.socket(socket.AF_UNIX) as server:
                    server.bind(path)
                    server.listen(1)
                    received = []

                    def reply():
                        conn, _ = server.accept()
                        with conn, conn.makefile("rb") as stream:
                            received.append(json.loads(stream.readline()))
                            conn.sendall(json.dumps({"id": "hypr-focus", "result": {
                                "type": "pane_focus_direction", "focus": {
                                    "changed": changed, "reason": None if changed else "no_neighbor"
                                }}}).encode() + b"\n")

                    thread = threading.Thread(target=reply)
                    thread.start()
                    self.assertEqual(focus.focus_pane(path, "left"), changed)
                    thread.join(2)
                    self.assertEqual(received[0]["params"], {"direction": "left"})

    def test_neighbor_stays_inside_and_border_dispatches_all_directions(self):
        for changed in (True, False):
            for direction in ("left", "right", "up", "down"):
                with self.subTest(changed=changed, direction=direction):
                    def hypr(*args):
                        return json.dumps([] if args[0] == "clients" else {"address": "0x1"})

                    with patch.object(focus, "hypr", side_effect=hypr) as ctl, \
                            patch.object(focus, "find_socket", return_value="/work.sock"), \
                            patch.object(focus, "processes", return_value={}), \
                            patch.object(focus, "focus_pane", return_value=changed), \
                            patch("sys.argv", [str(HELPER), direction]):
                        focus.main()
                        dispatches = [c.args for c in ctl.call_args_list if c.args[0] == "dispatch"]
                        self.assertEqual(dispatches, [] if changed else [
                            ("dispatch", 'hl.dsp.focus({ direction = "' + direction + '" })')])


if __name__ == "__main__":
    unittest.main()
