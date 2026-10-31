#!/bin/sh

# mise postinstall hook for herdr. mise first installs the upstream release
# binary. This hook then builds the same upstream release from source with
# pane-mute.patch and puts the patched binary in its place. See README.md.
#
# mise supplies MISE_TOOL_VERSION and MISE_TOOL_INSTALL_PATH. Any failure
# exits non-zero. mise then keeps that version incomplete, so the previous
# working Herdr stays selected. The executable changes only after the patch
# applies, its tests pass, the release builds, and `herdr --version` runs.
#
# The hook never touches a running Herdr server. A running server keeps the
# old binary until the user restarts it.

set -eu

hook_directory=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
patch_file="$hook_directory/pane-mute.patch"
version="${MISE_TOOL_VERSION:-}"
install_directory="${MISE_TOOL_INSTALL_PATH:-}"
installed_binary="$install_directory/herdr"
stamp_file="$install_directory/herdr-local.stamp"
source_url="https://github.com/herdrdev/herdr/archive/refs/tags/v$version.tar.gz"
patch_test_filter="notification_policy::pane_mute_tests::"

work_directory=""
staged_binary=""
staged_stamp=""
current_step="check the mise environment"

cleanup() {
    if [ -n "$work_directory" ]; then
        rm -rf "$work_directory"
    fi
    rm -f "$staged_binary" "$staged_stamp"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

fail() {
    echo "herdr-local: step \"$current_step\" failed for Herdr ${version:-(unknown version)}: $*" >&2
    echo "herdr-local: $installed_binary did not change." >&2
    exit 1
}

start_step() {
    current_step="$1"
    echo "herdr-local: $current_step" >&2
}

find_rustup() {
    if command -v rustup >/dev/null 2>&1; then
        command -v rustup
        return 0
    fi
    # rustup-init puts rustup here. Homebrew keeps its rustup keg-only.
    for candidate in "${CARGO_HOME:-$HOME/.cargo}/bin/rustup" \
        /opt/homebrew/opt/rustup/bin/rustup /usr/local/opt/rustup/bin/rustup; do
        if [ -x "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

# Prints the hex digest only. Fails when the hash command fails.
sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        hash_line=$(sha256sum "$1") || return 1
    else
        hash_line=$(shasum -a 256 "$1") || return 1
    fi
    hash_value=${hash_line%% *}
    case "$hash_value" in
        *[!0-9a-f]* | "") return 1 ;;
    esac
    [ ${#hash_value} -eq 64 ] || return 1
    echo "$hash_value"
}

# -------------------------------------------------------------- environment

[ -n "$version" ] || fail "MISE_TOOL_VERSION is empty. Run this hook through mise install."
[ -n "$install_directory" ] || fail "MISE_TOOL_INSTALL_PATH is empty. Run this hook through mise install."
[ -x "$installed_binary" ] || fail "mise installed no executable at $installed_binary."
[ -f "$patch_file" ] || fail "the patch $patch_file is missing. Run stow.fish to link the mise package."

# ------------------------------------------------------------ prerequisites

start_step "check the prerequisites"
for command_name in curl tar git; do
    command -v "$command_name" >/dev/null 2>&1 ||
        fail "$command_name is not on PATH. Install it with the system layer of !install (brew.sh, paru.fish, or apt/ubuntu.fish)."
done
command -v sha256sum >/dev/null 2>&1 || command -v shasum >/dev/null 2>&1 ||
    fail "neither sha256sum nor shasum is on PATH. Install coreutils or perl with the system layer of !install."
rustup_command=$(find_rustup) ||
    fail "rustup is not installed. Install it with the system layer of !install (brew.sh, paru.fish, or apt/cargo.fish), then run: rustup default stable"
command -v zig >/dev/null 2>&1 ||
    fail "zig is not on PATH. Keep zig in [tools] of ~/.config/mise/config.toml and keep depends = [\"zig\"] on herdr."

work_directory=$(mktemp -d "${TMPDIR:-/tmp}/herdr-local.XXXXXX") ||
    fail "mktemp could not make a temporary directory."
source_directory="$work_directory/source"
# A shared CARGO_TARGET_DIR from the environment would keep build outputs.
CARGO_TARGET_DIR="$work_directory/target"
export CARGO_TARGET_DIR

# The build and the stamp use this copy, so a change to the patch during the
# build cannot give the stamp a hash of a patch that was not applied.
applied_patch="$work_directory/pane-mute.patch"
cp "$patch_file" "$applied_patch" || fail "could not copy $patch_file."
patch_hash=$(sha256_of "$applied_patch") || fail "could not calculate the SHA-256 hash of $patch_file."

# ------------------------------------------------------------------- source

start_step "download the source of v$version"
curl --fail --silent --show-error --location --retry 3 \
    --output "$work_directory/source.tar.gz" "$source_url" ||
    fail "could not download $source_url"

start_step "unpack the source"
mkdir "$source_directory" || fail "could not make $source_directory"
tar -xzf "$work_directory/source.tar.gz" -C "$source_directory" --strip-components=1 ||
    fail "could not unpack $source_url"

# git apply is all or nothing. An own repository keeps it inside this tree.
start_step "apply pane-mute.patch"
git init --quiet "$source_directory" || fail "git init failed in $source_directory"
git -C "$source_directory" apply --whitespace=nowarn "$applied_patch" ||
    fail "pane-mute.patch does not apply to Herdr $version. README.md, section \"Patch conflict\", tells you what to do."

# ---------------------------------------------------------------- toolchain

start_step "check the Zig version"
zig_manifest="$source_directory/vendor/libghostty-vt/build.zig.zon"
if [ -f "$zig_manifest" ]; then
    required_zig=$(sed -n 's/.*\.minimum_zig_version *= *"\([^"]*\)".*/\1/p' "$zig_manifest")
    actual_zig=$(zig version) || fail "zig version failed."
    required_series=$(echo "$required_zig" | cut -d . -f 1,2)
    case "$actual_zig" in
        "$required_series" | "$required_series".*) ;;
        *) fail "Herdr $version needs Zig $required_zig, but zig on PATH is $actual_zig. Set zig = \"$required_series\" in ~/.config/mise/config.toml, then run mise install again." ;;
    esac
fi

# The release names its Rust version in rust-toolchain.toml. rustup installs
# that toolchain when it is missing.
start_step "install the Rust toolchain of Herdr $version"
(cd "$source_directory" && "$rustup_command" toolchain install --profile minimal) ||
    fail "rustup could not install the toolchain from $source_directory/rust-toolchain.toml."
active_toolchain=$(cd "$source_directory" && "$rustup_command" show active-toolchain) ||
    fail "rustup show active-toolchain failed."
toolchain=${active_toolchain%% *}
# Run the toolchain binaries directly. Homebrew's rustup puts no rustc or
# cargo proxies in ~/.cargo/bin, so cargo could not find rustc otherwise.
toolchain_cargo=$("$rustup_command" which --toolchain "$toolchain" cargo) ||
    fail "rustup which found no cargo in the toolchain $toolchain."
PATH="${toolchain_cargo%/*}:$PATH"
export PATH

run_cargo() {
    (cd "$source_directory" && "$toolchain_cargo" "$@")
}

# -------------------------------------------------------------------- build

start_step "run the pane mute tests"
run_cargo test --locked --bin herdr "$patch_test_filter" >"$work_directory/test-output.txt" ||
    { cat "$work_directory/test-output.txt" >&2; fail "cargo test reported a failure."; }
cat "$work_directory/test-output.txt" >&2
# cargo test exits 0 when the filter matches no test.
grep -Eq '^test result: ok\. [1-9][0-9]* passed; 0 failed' "$work_directory/test-output.txt" ||
    fail "cargo test ran no test that matches $patch_test_filter."

start_step "build the release"
run_cargo build --release --locked --bin herdr || fail "cargo build --release failed."
built_binary="$CARGO_TARGET_DIR/release/herdr"
[ -x "$built_binary" ] || fail "cargo build made no executable at $built_binary."

start_step "check that the patched binary starts"
version_output=$("$built_binary" --version) || fail "herdr --version exited non-zero."
case "$version_output" in
    *"$version"*) ;;
    *) fail "herdr --version printed \"$version_output\", not version $version." ;;
esac

# ------------------------------------------------------------------ install

# Stage both files in the install directory, so each mv is one rename on the
# same file system. The old stamp goes first: a stamp must never describe a
# binary that it does not belong to.
start_step "install the patched binary"
staged_binary="$install_directory/.herdr-local.binary.$$"
staged_stamp="$install_directory/.herdr-local.stamp.$$"
cp "$built_binary" "$staged_binary" || fail "could not copy the binary to $install_directory."
chmod 755 "$staged_binary" || fail "could not make $staged_binary executable."
printf 'upstream_version=%s\npatch_sha256=%s\n' "$version" "$patch_hash" >"$staged_stamp" ||
    fail "could not write the stamp file."
if [ -e "$stamp_file" ] || [ -L "$stamp_file" ]; then
    rm -f "$stamp_file" && [ ! -e "$stamp_file" ] || fail "could not remove the old stamp file $stamp_file."
fi
mv -f "$staged_binary" "$installed_binary" || fail "could not replace $installed_binary."
if ! mv -f "$staged_stamp" "$stamp_file"; then
    echo "herdr-local: the patched binary is installed, but the stamp file $stamp_file could not be written." >&2
    exit 1
fi

echo "herdr-local: installed patched Herdr $version in $install_directory" >&2
