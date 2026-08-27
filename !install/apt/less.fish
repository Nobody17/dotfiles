#!/usr/bin/env fish

# Build a current less from source, configured to open its editor as hx.
# lazygit itself comes from mise; this script used to install both.

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
