#!/usr/bin/env fish

# Install rustup before mise. Keep a default toolchain for commands that run
# outside mise. mise.fish installs the configured Rust toolchain afterward;
# use mise up to update it along with the other tools.

if not command -v rustup > /dev/null
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y || exit 1
end

if test -f "$HOME/.cargo/env.fish"
    source "$HOME/.cargo/env.fish"
end

if not rustup default > /dev/null 2>&1
    rustup default stable; or exit 1
end
