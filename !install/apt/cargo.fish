#!/usr/bin/env fish

# rustup only. Every other tool this script used to cargo-install
# (fd, taplo, eza, zoxide, delta, ripgrep) now comes from mise.
# rust stays with rustup because components (clippy, rust-analyzer)
# and cross-compilation targets need rustup itself.

if not command -v rustup > /dev/null
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y || exit 1
end

if test -f "$HOME/.cargo/env.fish"
    source "$HOME/.cargo/env.fish"
end

rustup default stable
rustup update
