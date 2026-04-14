#!/bin/bash

# 1. Den Rust-Pfad ganz am Anfang für das gesamte Skript erzwingen
export PATH="$HOME/.cargo/bin:$PATH"

if ! command -v cargo &> /dev/null; then
    echo "Installiere Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi

if ! rustup default &> /dev/null; then
    echo "Setze Rust Standard-Toolchain..."
    rustup default stable
fi

if [ -f /etc/arch-release ]; then
    echo "Detected Arch-based system..."
    # gettext für Arch hinzugefügt
    sudo pacman -Syu --needed base-devel ncurses cmake gettext
elif [ -f /etc/debian_version ]; then
    echo "Detected Debian/Ubuntu-based system..."
    sudo apt update
    # 2. gettext für Debian hinzugefügt (behebt die msgfmt Warnung)
    sudo apt install -y make cmake build-essential libncurses-dev curl gettext
else
    echo "Unsupported distribution. Please install dependencies manually."
    exit 1
fi

fish_source_url=$(curl -s https://api.github.com/repos/fish-shell/fish-shell/releases/latest | grep "browser_download_url" | grep -v "linux" | grep -oE "https://[^ ]+\.tar\.xz" | head -n 1)

echo "Lade Fish herunter: $fish_source_url"
curl -L "$fish_source_url" -o fish.tar.xz

# 3. Vorherigen Build-Ordner mit sudo entfernen, falls er noch root gehört
sudo rm -rf fish_build
mkdir -p fish_build
tar -xf fish.tar.xz -C fish_build --strip-components=1

cd fish_build

# 4. Der Magic-Fix: Wir geben CMake den exakten Pfad zu Cargo hart codiert mit!
cmake -DRust_CARGO_CACHED="$HOME/.cargo/bin/cargo" .
cmake --build .
sudo cmake --install .
cd ..

sudo rm -rf fish_build fish.tar.xz

# Check if running in WSL
if [ -f /proc/sys/fs/binfmt_misc/WSLInterop ] || grep -qi microsoft /proc/version; then
    # Ensure /usr/local/bin/fish is in /etc/shells so chsh accepts it
    if ! grep -q "/usr/local/bin/fish" /etc/shells; then
        echo "/usr/local/bin/fish" | sudo tee -a /etc/shells
    fi
    
    sudo chsh -s /usr/local/bin/fish "$USER"
fi

echo "Installation complete! Restart your terminal or type 'fish' to begin."
