#!/usr/bin/env fish
if command -v paru > /dev/null
    echo "Paru detected. Installing asdf-vm and dependencies via AUR..."

    paru --needed base-devel asdf-vm ncurses glu mesa wxwidgets-gtk3 libpng libssh unixodbc libxslt fop

    if test -f /opt/asdf-vm/asdf.fish
        source /opt/asdf-vm/asdf.fish
    end

else if command -v apt > /dev/null
    go install github.com/asdf-vm/asdf/cmd/asdf@v0.18.1
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
