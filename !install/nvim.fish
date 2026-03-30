#!/usr/bin/env fish

if command -v paru > /dev/null
    paru -S --needed neovim
else
    set -l neovim_archive_filename "nvim-linux-x86_64.tar.gz"
    set -l neovim_download_url "https://github.com/neovim/neovim/releases/latest/download/$neovim_archive_filename"
    set -l neovim_installation_directory "/opt/nvim"

    curl -LO $neovim_download_url
    sudo rm -rf $neovim_installation_directory
    sudo mkdir -p $neovim_installation_directory
    sudo tar -C $neovim_installation_directory --strip-components=1 -xzf $neovim_archive_filename
    fish_add_path -gP "$neovim_installation_directory/bin"
    rm $neovim_archive_filename
end

if command -v nvim > /dev/null
    echo "Success: "(nvim --version | head -n 1)" is ready to use."
else
    exit 1
end
