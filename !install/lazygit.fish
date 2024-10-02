#!/usr/bin/env fish

set LAZYGIT_VERSION (curl -s "https://api.github.com/repos/jesseduffield/lazygit/releases/latest" | grep -Po '"tag_name": "v\K[^"]*')
curl -Lo lazygit.tar.gz "https://github.com/jesseduffield/lazygit/releases/latest/download/lazygit_{$LAZYGIT_VERSION}_Linux_x86_64.tar.gz"
tar xf lazygit.tar.gz lazygit
sudo install lazygit /usr/local/bin
rm -rf lazygit
rm lazygit.tar.gz

set LESS_VERSION (curl https://www.greenwoodsoftware.com/less/download.html | grep "Download <strong>RECOMMENDED" | cut -d '>' -f 4 | cut -d ' ' -f 3)
curl -JLo less.tar.gz "https://www.greenwoodsoftware.com/less/less-{$LESS_VERSION}.tar.gz"
curl -JLo less.sig "https://www.greenwoodsoftware.com/less/less-{$LESS_VERSION}.sig"
curl -LJO https://ftp.gnu.org/gnu/gnu-keyring.gpg
if not gpgv --keyring ./gnu-keyring.gpg less.sig less.tar.gz
    return 1
end
mkdir -p less
tar -xf less.tar.gz -C less --strip-components=1
cd less
sh configure --with-editor=hx
make
sudo make install
cd ..
rm gnu-keyring.gpg
rm less.sig less.tar.gz
rm -rf less

# Install delta with cargo
# set DELTA_VERSION (curl -s "https://api.github.com/repos/dandavison/delta/releases/latest" | grep -Po '"tag_name": "\K[^"]*')
# curl -Lo delta.tar.gz "https://github.com/jesseduffield/lazygit/releases/latest/download/delta-{$DELTA_VERSION}-x86_64-unknown-linux-gnu.tar.gz"
# tar xf delta.tar.gz
