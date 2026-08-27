#!/usr/bin/env fish

# Debian/Ubuntu system layer. bat used to be installed here (with a
# batcat -> bat symlink); mise provides it now, on every platform.

sudo apt update
sudo apt install -y build-essential libreadline-dev
sudo apt install -y git curl unzip xclip
sudo apt install -y lua5.1 liblua5.1-dev
sudo apt install -y sqlite3
sudo apt install -y perl latexmk
sudo apt install -y gettext
sudo apt install -y zathura
