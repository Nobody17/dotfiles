#!/usr/bin/env fish
sudo apt update
sudo apt install git curl unzip xclip
sudo apt install lua5.4
sudo apt install bat
sudo apt install python3.12-venv
mkdir -p ~/.local/bin
ln -s /usr/bin/batcat ~/.local/bin/bat
