#!/usr/bin/env fish
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup update
source "$HOME/.cargo/env.fish"

cargo install fd-find
if test -e /usr/bin/fdfind
    mkdir -p ~/.local/bin
    ln -s /usr/bin/fdfind ~/.local/bin/fd
end
cargo install taplo-cli --locked
cargo install eza
cargo install zoxide --locked
cargo install --locked yazi-fm yazi-cli
cargo install --locked zellij
cargo install git-delta
cargo install ripgrep
