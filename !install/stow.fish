#!/usr/bin/env fish

curl -LJO http://ftp.gnu.org/gnu/stow/stow-latest.tar.gz
curl -LJO http://ftp.gnu.org/gnu/stow/stow-latest.tar.gz.sig
curl -LJO https://ftp.gnu.org/gnu/gnu-keyring.gpg
if not gpgv --keyring ./gnu-keyring.gpg stow-latest.tar.gz.sig stow-latest.tar.gz
    return 1
end
sudo cpan Test:Output
sudo cpan Test:More
mkdir stow
tar -xf stow-latest.tar.gz -C stow --strip-components=1
cd stow
and ./configure
and sudo make install
cd ..
rm -rf stow
rm stow-latest.tar.gz
rm stow-latest.tar.gz.sig
rm gnu-keyring.gpg
