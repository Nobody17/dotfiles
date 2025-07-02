#!/usr/bin/env fish

set -l filename nvim-linux-x86_64.tar.gz
curl -LO https://github.com/neovim/neovim/releases/latest/download/$filename
sudo rm -rf /opt/nvim
sudo mkdir /opt/nvim
sudo tar -C /opt/nvim --strip-components=1 -xzf $filename
fish_add_path -gP /opt/nvim/bin
sudo rm $filename
