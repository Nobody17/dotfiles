#!/usr/bin/env fish
if type -q pacman
    echo "Arch-based system detected. Proceeding..."
else
    echo "Error: pacman not found. This script (paru installation) requires an Arch-based distribution."
    exit 1
end

sudo pacman -S --needed base-devel git
git clone https://aur.archlinux.org/paru.git
cd paru
makepkg -si
cd ..
rm -rf paru

# System layer only. Language runtimes and CLI tools come from mise, so
# they are deliberately absent here: node, python, go, ruby, erlang,
# elixir, delta, lazygit, lazydocker, eza, zoxide, ripgrep, fd, fzf, bat,
# yazi, yq, taplo, starship, neovim, gh, uv. See mise/.config/mise/config.toml.

# Build toolchain
paru -S --needed cmake cpio meson unzip

# Erlang build dependencies. mise compiles Erlang from source, so these
# must exist before `mise install` runs.
paru -S --needed ncurses glu mesa wxwidgets-gtk3 libpng libssh unixodbc libxslt fop

# rustup owns rust; mise defers to it.
paru -S --needed rustup

# JDK 17 for Gradle, reached through JAVA_HOME only. Not from mise:
# mise only offers openjdk-17.0.2, unpatched since 2022.
paru -S --needed jdk17-openjdk

# Terminal. ghostty-terminfo and ghostty-shell-integration come with it as
# hard dependencies. On macOS use "brew install --cask ghostty" instead.
paru -S --needed ghostty

# Bootstrap: stow links this repo, mise installs everything else.
paru -S --needed stow mise

# SSH security keys
paru -S --needed libfido2
