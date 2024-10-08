#!/usr/bin/env fish
sudo apt update
sudo apt install git curl unzip
sudo apt install lua5.4
sudo apt install bat
mkdir -p ~/.local/bin
ln -s /usr/bin/batcat ~/.local/bin/bat
