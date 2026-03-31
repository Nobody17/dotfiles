#!/bin/bash
if [ -f /etc/arch-release ]; then
    echo "Detected Arch-based system..."
    sudo pacman -Syu --needed base-devel ncurses cmake
elif [ -f /etc/debian_version ]; then
    echo "Detected Debian/Ubuntu-based system..."
    sudo apt update
    sudo apt install -y make cmake build-essential libncurses-dev curl
else
    echo "Unsupported distribution. Please install dependencies manually."
    exit 1
fi

fish_source_url=$(curl -s https://api.github.com/repos/fish-shell/fish-shell/releases/latest | grep "browser_download_url" | grep -oE "https://[^ ]+\.tar\.xz")

curl -L "$fish_source_url" -o fish.tar.xz
mkdir -p fish_build
tar -xf fish.tar.xz -C fish_build --strip-components=1

cd fish_build
cmake .
make
sudo make install
cd ..

rm -rf fish_build fish.tar.xz

# Check if running in WSL
if [ -f /proc/sys/fs/binfmt_misc/WSLInterop ] || grep -qi microsoft /proc/version; then
    # Ensure /usr/local/bin/fish is in /etc/shells so chsh accepts it
    if ! grep -q "/usr/local/bin/fish" /etc/shells; then
        echo "/usr/local/bin/fish" | sudo tee -a /etc/shells
    fi
    
    sudo chsh -s /usr/local/bin/fish "$USER"
fi

echo "Installation complete! Restart your terminal or type 'fish' to begin."
