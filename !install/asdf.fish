#!/usr/bin/env fish

set ASDF_URL (curl -s "https://api.github.com/repos/asdf-vm/asdf/releases/latest" | grep tarball_url | cut -d '"' -f 4)
curl -Lo asdf.tar.gz $ASDF_URL
mkdir -p asdf
tar xf asdf.tar.gz -C asdf --strip-components=1
and test -d ~/.asdf && rm -rf ~/.asdf
mv asdf/ ~/.asdf/
rm asdf.tar.gz

source ~/.asdf/asdf.fish

sudo apt -y install build-essential autoconf m4 libncurses5-dev libwxgtk3.2-dev libwxgtk-webview3.2-dev libgl1-mesa-dev libglu1-mesa-dev libpng-dev libssh-dev unixodbc-dev xsltproc fop libxml2-utils libncurses-dev openjdk-11-jdk unzip
and asdf plugin add erlang https://github.com/asdf-vm/asdf-erlang.git

asdf install erlang latest
asdf global erlang latest

asdf plugin-add elixir https://github.com/asdf-vm/asdf-elixir.git
asdf install elixir latest
asdf global elixir latest
