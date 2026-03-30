#!/usr/bin/env fish
if command -v paru > /dev/null
    echo "Paru detected. Installing asdf-vm and dependencies via AUR..."

    paru --needed base-devel asdf-vm ncurses glu mesa wxwidgets-gtk3 libpng libssh unixodbc libxslt fop

    if test -f /opt/asdf-vm/asdf.fish
        source /opt/asdf-vm/asdf.fish
    end

else if command -v apt > /dev/null
    echo "Apt detected. Installing asdf manually and dependencies via repository..."

    # Manual installation of asdf via GitHub
    set -l asdf_latest_release_url (curl -s "https://api.github.com/repos/asdf-vm/asdf/releases/latest" | grep tarball_url | cut -d '"' -f 4)
    curl -Lo asdf_archive.tar.gz $asdf_latest_release_url

    mkdir -p asdf_temporary_directory
    tar xf asdf_archive.tar.gz -C asdf_temporary_directory --strip-components=1

    # Clean old installation if exists
    if test -d ~/.asdf
        rm -rf ~/.asdf
    end

    mv asdf_temporary_directory/ ~/.asdf/
    rm asdf_archive.tar.gz

    # Source the manual installation
    source ~/.asdf/asdf.fish

    # Install Erlang/Elixir dependencies via apt
    sudo apt update
    sudo apt -y install build-essential autoconf m4 libncurses5-dev libwxgtk3.2-dev \
        libwxgtk-webview3.2-dev libgl1-mesa-dev libglu1-mesa-dev libpng-dev \
        libssh-dev unixodbc-dev xsltproc fop libxml2-utils libncurses-dev \
        openjdk-11-jdk unzip
else
    echo "Error: Neither 'paru' nor 'apt' was found. This script only supports Arch or Debian-based systems."
    exit 1
end

function install_asdf_plugin
    set -l plugin_name $argv[1]
    set -l plugin_url $argv[2]
    if not asdf plugin list | grep -q $plugin_name
        asdf plugin add $plugin_name $plugin_url
    end
end

install_asdf_plugin erlang https://github.com/asdf-vm/asdf-erlang.git
asdf install erlang latest
asdf set -u erlang latest

install_asdf_plugin elixir https://github.com/asdf-vm/asdf-elixir.git
asdf install elixir latest
asdf set -u elixir latest

echo "Setup complete! Erlang and Elixir are ready to use."
