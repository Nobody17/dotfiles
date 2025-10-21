#!/usr/bin/env fish

curl -LO https://github.com/neovim/neovim/releases/latest/download/nvim-linux-x86_64.tar.gz
sudo rm -rf /opt/nvim
sudo tar -C /opt -xzf nvim-linux-x86_64.tar.gz
fish_add_path /opt/nvim-linux-x86_64/bin
sudo rm nvim-linux-x86_64.tar.gz
