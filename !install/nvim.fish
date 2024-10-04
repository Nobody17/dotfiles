#!/usr/bin/env fish

curl -LO https://github.com/neovim/neovim/releases/latest/download/nvim-linux64.tar.gz
sudo rm -rf /opt/nvim
sudo tar -C /opt -xzf nvim-linux64.tar.gz
fish_add_path /opt/nvim-linux64/bin
sudo rm nvim-linux64.tar.gz

sudo apt install git make unzip gcc xclip
git clone https://github.com/nvim-lua/kickstart.nvim.git $HOME/.config/nvim
cd $HOME/.config/nvim
git pull
cd -
nvim
