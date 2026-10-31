"""Run with python3 -m unittest discover -s '!tests' -p 'test_herdr_local_postinstall.py'.

Runs the mise postinstall hook of herdr as a process. Stubs replace curl,
rustup, cargo, and zig, so no download or compilation takes place. A small test patch
replaces pane-mute.patch, so these tests do not depend on the Herdr source.
"""

import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import textwrap
import unittest

HOOK = Path(__file__).resolve().parents[1] / "mise/.config/mise/herdr-local/postinstall.sh"
VERSION = "0.9.9"
SOURCE_URL = f"https://github.com/herdrdev/herdr/archive/refs/tags/v{VERSION}.tar.gz"
PREVIOUS_BINARY = b"#!/bin/sh\necho 'herdr previous'\n"
UPSTREAM_MAIN = "fn main() {\n    sound();\n}\n"
TEST_PATCH = textwrap.dedent("""\
    diff --git a/src/main.rs b/src/main.rs
    --- a/src/main.rs
    +++ b/src/main.rs
    @@ -1,3 +1,3 @@
     fn main() {
    -    sound();
    +    sound_unless_muted();
     }
    """)

# Each stub appends one line per call to $STUB_LOG.
CURL_STUB = """\
#!/bin/sh
output=""
url=""
while [ $# -gt 0 ]; do
    case "$1" in
        --output) output="$2"; shift 2 ;;
        -*) shift ;;
        *) url="$1"; shift ;;
    esac
done
echo "curl $url" >>"$STUB_LOG"
cp "$STUB_TARBALL" "$output"
"""

ZIG_STUB = """\
#!/bin/sh
echo "zig $*" >>"$STUB_LOG"
echo 0.16.0
"""

# rustup only installs and names the toolchain. Its cargo stands in for the
# real build. Like the real cargo, it needs rustc on PATH. The fake release
# binary prints the patched line, so a test can see which source it came from.
RUSTUP_STUB = """\
#!/bin/sh
echo "rustup $* (in $PWD)" >>"$STUB_LOG"
case "$1 $2" in
    "toolchain install") exit 0 ;;
    "show active-toolchain") echo "1.96.1-stub (overridden by '$PWD/rust-toolchain.toml')"; exit 0 ;;
    "which --toolchain") [ "$3" = 1.96.1-stub ] && echo "$STUB_TOOLCHAIN_BIN/$4" && exit 0 ;;
esac
exit 90
"""

CARGO_STUB = """\
#!/bin/sh
echo "cargo $* (in $PWD)" >>"$STUB_LOG"
command -v rustc >/dev/null 2>&1 || { echo "error: could not execute process rustc -vV" >&2; exit 101; }
case "$1" in
    test)
        [ -z "${STUB_TEST_FAILS:-}" ] || { echo "test result: FAILED. 4 passed; 1 failed"; exit 101; }
        echo "test result: ok. ${STUB_TEST_COUNT:-5} passed; 0 failed; 0 ignored"
        ;;
    build)
        [ -z "${STUB_BUILD_FAILS:-}" ] || { echo "error: could not compile herdr" >&2; exit 101; }
        [ -z "${STUB_CHANGE_PATCH:-}" ] || echo "# edited during the build" >>"$STUB_CHANGE_PATCH"
        mkdir -p "$CARGO_TARGET_DIR/release"
        {
            echo '#!/bin/sh'
            echo "echo 'herdr ${STUB_BUILT_VERSION:-0.9.9}'"
            sed 's/^/# /' src/main.rs
        } >"$CARGO_TARGET_DIR/release/herdr"
        chmod 755 "$CARGO_TARGET_DIR/release/herdr"
        ;;
    *) exit 91 ;;
esac
"""


class PostinstallHookTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="herdr local ")
        self.addCleanup(temporary.cleanup)
        # A path with spaces, like a checkout in "~/My Dotfiles".
        self.root = Path(temporary.name) / "dot files"
        self.hook_directory = self.root / "config/mise/herdr-local"
        self.hook_directory.mkdir(parents=True)
        self.hook = self.hook_directory / "postinstall.sh"
        shutil.copy(HOOK, self.hook)
        self.patch_file = self.hook_directory / "pane-mute.patch"
        self.patch_file.write_text(TEST_PATCH)

        self.install_directory = self.root / "mise data/installs/herdr" / VERSION
        self.install_directory.mkdir(parents=True)
        self.binary = self.install_directory / "herdr"
        self.binary.write_bytes(PREVIOUS_BINARY)
        self.binary.chmod(0o755)
        self.stamp = self.install_directory / "herdr-local.stamp"

        self.stub_directory = self.root / "stubs"
        self.stub_directory.mkdir()
        # The toolchain folder is not on PATH, as with Homebrew's rustup.
        self.toolchain_directory = self.root / "rustup/toolchains/1.96.1-stub/bin"
        self.toolchain_directory.mkdir(parents=True)
        for directory, name, content in (
                (self.stub_directory, "curl", CURL_STUB),
                (self.stub_directory, "zig", ZIG_STUB),
                (self.stub_directory, "rustup", RUSTUP_STUB),
                (self.toolchain_directory, "cargo", CARGO_STUB),
                (self.toolchain_directory, "rustc", "#!/bin/sh\nexit 0\n")):
            stub = directory / name
            stub.write_text(content)
            stub.chmod(0o755)
        self.stub_log = self.root / "stub.log"
        self.tarball = self.root / "source.tar.gz"
        self.temporary_directory = self.root / "tmp"
        self.temporary_directory.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()

    def write_tarball(self, main_source):
        files = {
            "src/main.rs": main_source,
            "rust-toolchain.toml": '[toolchain]\nchannel = "1.96.1"\n',
            "vendor/libghostty-vt/build.zig.zon": '.{\n    .minimum_zig_version = "0.16.0",\n}\n',
        }
        with tarfile.open(self.tarball, "w:gz") as archive:
            for name, content in files.items():
                data = content.encode()
                info = tarfile.TarInfo(f"herdr-{VERSION}/{name}")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))

    def run_hook(self, **stub_settings):
        environment = {
            "PATH": f"{self.stub_directory}:/usr/bin:/bin",
            "HOME": str(self.home),
            "TMPDIR": str(self.temporary_directory),
            "MISE_TOOL_NAME": "herdr",
            "MISE_TOOL_VERSION": VERSION,
            "MISE_TOOL_INSTALL_PATH": str(self.install_directory),
            "STUB_LOG": str(self.stub_log),
            "STUB_TARBALL": str(self.tarball),
            "STUB_TOOLCHAIN_BIN": str(self.toolchain_directory),
            **stub_settings,
        }
        return subprocess.run(["sh", str(self.hook)], env=environment, capture_output=True,
                              text=True, timeout=30, check=False)

    def stub_calls(self):
        return self.stub_log.read_text().splitlines() if self.stub_log.exists() else []

    def assert_no_build_folder_left(self):
        # Only the hook's own folder counts: on macOS, /usr/bin/git can leave
        # an xcrun cache in TMPDIR.
        self.assertEqual(list(self.temporary_directory.glob("herdr-local.*")), [])

    def assert_previous_executable_intact(self, result):
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.binary.read_bytes(), PREVIOUS_BINARY)
        self.assertTrue(os.access(self.binary, os.X_OK))
        self.assertFalse(self.stamp.exists())
        self.assertEqual(sorted(path.name for path in self.install_directory.iterdir()), ["herdr"])
        self.assert_no_build_folder_left()

    def test_success_installs_the_patched_build_and_its_stamp(self):
        self.write_tarball(UPSTREAM_MAIN)
        self.stamp.write_text("upstream_version=0.9.8\npatch_sha256=old\n")

        result = self.run_hook()

        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.binary.read_text()
        self.assertIn("sound_unless_muted();", installed)
        self.assertNotIn("#     sound();", installed)
        self.assertTrue(os.access(self.binary, os.X_OK))
        patch_hash = hashlib.sha256(TEST_PATCH.encode()).hexdigest()
        self.assertEqual(self.stamp.read_text(),
                         f"upstream_version={VERSION}\npatch_sha256={patch_hash}\n")
        calls = self.stub_calls()
        self.assertEqual(calls[0], f"curl {SOURCE_URL}")
        cargo_calls = [call for call in calls if call.startswith("cargo ")]
        self.assertEqual(len(cargo_calls), 2)
        self.assertTrue(cargo_calls[0].startswith(
            "cargo test --locked --bin herdr notification_policy::pane_mute_tests:: (in "))
        self.assertTrue(cargo_calls[1].startswith("cargo build --release --locked --bin herdr (in "))
        self.assertEqual(sorted(path.name for path in self.install_directory.iterdir()),
                         ["herdr", "herdr-local.stamp"])
        self.assert_no_build_folder_left()

    def test_patch_conflict_keeps_the_previous_executable(self):
        self.write_tarball("fn main() {\n    play_sound();\n}\n")

        result = self.run_hook()

        self.assert_previous_executable_intact(result)
        self.assertIn('step "apply pane-mute.patch" failed for Herdr 0.9.9', result.stderr)
        self.assertFalse([call for call in self.stub_calls() if call.startswith("cargo ")])

    def test_build_failure_keeps_the_previous_executable(self):
        self.write_tarball(UPSTREAM_MAIN)

        result = self.run_hook(STUB_BUILD_FAILS="1")

        self.assert_previous_executable_intact(result)
        self.assertIn('step "build the release" failed for Herdr 0.9.9', result.stderr)

    def test_failing_or_missing_patch_tests_keep_the_previous_executable(self):
        for settings in ({"STUB_TEST_FAILS": "1"}, {"STUB_TEST_COUNT": "0"}):
            with self.subTest(settings=settings):
                self.stub_log.unlink(missing_ok=True)
                self.write_tarball(UPSTREAM_MAIN)

                result = self.run_hook(**settings)

                self.assert_previous_executable_intact(result)
                self.assertIn('step "run the pane mute tests" failed for Herdr 0.9.9', result.stderr)
                self.assertFalse([call for call in self.stub_calls() if call.startswith("cargo build")])

    def test_binary_that_reports_another_version_keeps_the_previous_executable(self):
        self.write_tarball(UPSTREAM_MAIN)

        result = self.run_hook(STUB_BUILT_VERSION="0.9.8")

        self.assert_previous_executable_intact(result)
        self.assertIn('step "check that the patched binary starts" failed for Herdr 0.9.9',
                      result.stderr)

    def test_stamp_records_the_patch_that_was_applied(self):
        self.write_tarball(UPSTREAM_MAIN)

        result = self.run_hook(STUB_CHANGE_PATCH=str(self.patch_file))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(self.patch_file.read_text(), TEST_PATCH)
        patch_hash = hashlib.sha256(TEST_PATCH.encode()).hexdigest()
        self.assertEqual(self.stamp.read_text(),
                         f"upstream_version={VERSION}\npatch_sha256={patch_hash}\n")

    def test_failing_hash_command_keeps_the_previous_executable(self):
        self.write_tarball(UPSTREAM_MAIN)
        for name in ("sha256sum", "shasum"):
            stub = self.stub_directory / name
            stub.write_text("#!/bin/sh\nexit 1\n")
            stub.chmod(0o755)

        result = self.run_hook()

        self.assert_previous_executable_intact(result)
        self.assertIn("SHA-256", result.stderr)

    def test_old_stamp_that_cannot_be_removed_keeps_the_previous_executable(self):
        self.write_tarball(UPSTREAM_MAIN)
        # rm -f cannot remove a folder, so the old stamp stays in place.
        self.stamp.mkdir()
        (self.stamp / "keep").write_text("")

        result = self.run_hook()

        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn('step "install the patched binary" failed for Herdr 0.9.9', result.stderr)
        self.assertEqual(self.binary.read_bytes(), PREVIOUS_BINARY)
        self.assertEqual(sorted(path.name for path in self.install_directory.iterdir()),
                         ["herdr", "herdr-local.stamp"])
        self.assert_no_build_folder_left()

    def test_missing_zig_names_the_mise_dependency(self):
        self.write_tarball(UPSTREAM_MAIN)
        (self.stub_directory / "zig").unlink()

        result = self.run_hook()

        self.assert_previous_executable_intact(result)
        self.assertIn('step "check the prerequisites" failed for Herdr 0.9.9', result.stderr)
        self.assertIn('depends = ["zig"]', result.stderr)
        self.assertEqual(self.stub_calls(), [])


if __name__ == "__main__":
    unittest.main()
