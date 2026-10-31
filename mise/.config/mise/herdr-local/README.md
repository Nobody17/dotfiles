# Local Herdr patch

`pane-mute.patch` is the local patch for Herdr 0.9.5. It changes only the client sound decision. A patched client plays no completion sound and no needs-input sound for a pane that has the metadata token `dotfiles_pane_mute`. Toasts, notification navigation, agent status, wait behavior, and terminal bells do not change. The patch does not change the server, the wire protocol, or the CLI.

Mute and unmute a pane with the existing Herdr command:

```sh
herdr pane report-metadata <pane_id> --source dotfiles:pane-mute --token dotfiles_pane_mute=1
herdr pane report-metadata <pane_id> --source dotfiles:pane-mute --clear-token dotfiles_pane_mute
```

The client reads the token from the last snapshot that it received from the server. A pane without an agent entry in that snapshot counts as unmuted. When a state change comes within one render interval of the mute (normally 16 ms), the notification can arrive before the snapshot with the token, and the sound can still play. This is a known limitation.

## Behavioral tests

Apply the patch to the source of the matching upstream release, then run the tests from the root of that source tree:

```sh
cargo test --locked --bin herdr notification_policy::pane_mute_tests::
```

The build needs the Rust and Zig versions that the release requires (Herdr 0.9.5: Rust 1.96.1, Zig 0.16.0 on `PATH`). The command exits non-zero when a test fails. But it exits 0 when the filter matches no test, so also check that the summary line reports `5 passed`.

## Installation through mise

`~/.config/mise/config.toml` gives herdr the postinstall hook `postinstall.sh` from this folder. mise first installs the upstream release binary. The hook then builds the same release with the patch and replaces that binary. Steps of the hook:

1. Download the source of the tag `v<version>` from GitHub as a tar archive. This needs no GitHub CLI and no credentials.
2. Apply `pane-mute.patch`.
3. Install the Rust toolchain that the release names in `rust-toolchain.toml`, through rustup.
4. Run the behavioral tests above. At least one test must run.
5. Build the release, then run `herdr --version` on the new binary.
6. Replace the executable and write the stamp file `herdr-local.stamp` next to it.

The hook builds in a temporary folder and removes that folder at the end. It keeps no build cache. A run takes some minutes.

When a step fails, the hook names the step and the version and exits non-zero. The executable stays as it was. mise then keeps that version incomplete: `latest` still selects the previous working version, and the next `mise install` tries the failed version again.

### Prerequisites

The bootstrap order in `!install/install.fish` supplies them:

1. System layer: `curl`, `tar`, `git`, a C compiler, and rustup with a default toolchain (`brew.sh`, `paru.fish`, or `apt/ubuntu.fish` with `apt/cargo.fish`). The hook finds rustup on `PATH`, in `~/.cargo/bin`, or in the Homebrew keg.
2. `stow.fish` links this folder to `~/.config/mise/herdr-local`.
3. mise installs `zig` before herdr (`depends = ["zig"]`). Keep `zig` at the series that the Herdr release asks for. The hook reads the required version from `vendor/libghostty-vt/build.zig.zon` and stops with the value to set when the series differs.

When a prerequisite is missing, the hook stops before the download and tells you how to install it.

The hook downloads the source without the GitHub API. But mise itself asks the GitHub API for the herdr release before the hook runs. Without credentials, GitHub allows 60 API requests an hour, and a first `mise install` of the whole configuration can use them up. herdr then fails with `403 Forbidden` for `api.github.com`. Wait for the reset, or sign in with `gh auth login`, then run `mise install` again.

### Normal updates

Use mise as usual:

```sh
mise up herdr      # or: mise up, mise install
```

Every new Herdr version goes through the hook. A running Herdr server keeps its old binary until you restart it. The hook never stops a server and never closes a pane. Restart the server when you are ready to use the new build.

### Check the stamp of the active build

```sh
cat "$(mise where herdr)/herdr-local.stamp"
shasum -a 256 ~/.config/mise/herdr-local/pane-mute.patch   # Linux: sha256sum
```

The stamp gives `upstream_version` and `patch_sha256`. The build is current when `upstream_version` is the version that `mise current herdr` shows and `patch_sha256` is the hash of the patch file. No stamp file means that the binary is not a verified patched build: either the unpatched upstream release, or an installation that stopped before it wrote the stamp.

### Patch conflict

When upstream changes the patched code, the hook stops at `apply pane-mute.patch`. Your previous Herdr stays selected, so there is no hurry. To repair the patch, let git merge it onto the new release. Run these commands in `sh`. Set `old` to the version that the first line of `pane-mute.patch` names and `new` to the version that failed:

```sh
old=0.9.5 new=0.9.6
patch_file=~/.config/mise/herdr-local/pane-mute.patch
mkdir herdr-repair && cd herdr-repair && git init --quiet
curl -fsSL "https://github.com/herdrdev/herdr/archive/refs/tags/v$old.tar.gz" | tar -xz --strip-components=1
git add --all --force && git commit --quiet -m "upstream $old"
git switch --quiet --create patched
git apply "$patch_file" && git add --all --force && git commit --quiet -m "pane mute"
git switch --quiet --create upgrade HEAD~1
git rm -r --quiet . && curl -fsSL "https://github.com/herdrdev/herdr/archive/refs/tags/v$new.tar.gz" | tar -xz --strip-components=1
git add --all --force && git commit --quiet -m "upstream $new"
git cherry-pick patched
```

When `git cherry-pick` reports a conflict, fix the files, then run `git add --all` and `git cherry-pick --continue`. Then:

1. Run the behavioral tests above in `herdr-repair`.
2. Write the new patch: `{ sed -n 1,2p "$patch_file"; git diff HEAD~1; } > new.patch`. Change the version in its first line and in this README, then replace `pane-mute.patch` with it.
3. Commit the patch in the dotfiles repository, then run `mise install herdr`.

To stay on the previous version instead, pin it in `config.toml`, for example `version = "0.9.5"`.

### Initial adoption on a computer that already has Herdr

mise runs the hook only when it installs a version. A Herdr version that mise installed before this hook existed stays unpatched. Do not force a reinstall of that version: mise can remove the working copy before the build succeeds. Run the hook by hand on the installed version instead:

```sh
./stow.fish        # in the dotfiles repository: links herdr-local
mise install zig
mise exec zig -- env MISE_TOOL_VERSION="$(mise current herdr)" MISE_TOOL_INSTALL_PATH="$(mise where herdr)" sh ~/.config/mise/herdr-local/postinstall.sh
```

The hook stages the new binary in the install folder and renames it over the old one only after all checks pass. Running servers keep the old binary until you restart them. Then check the stamp as shown above.
