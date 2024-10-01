#! /bin/bash 

fish_source_url=$(curl -s https://api.github.com/repos/fish-shell/fish-shell/releases/latest | grep browser_download_url | grep '\.tar\.xz"' | cut -d '"' -f 4)
curl "$fish_source_url" -LJo fish.tar.xz
mkdir fish
tar -xf fish.tar.xz -C fish --strip-components=1
cd fish
cmake .
make
sudo make install
cd ..
rm -rf fish
rm fish.tar.xz

echo 'sudo chsh -s /usr/bin/fish username to start fish with wsl'
echo 'git config --global credential.helper "/mnt/c/Program\ Files/Git/mingw64/libexec/git-core/git-credential-wincred.exe" for git credentials in WSL'
