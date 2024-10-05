#!/usr/bin/env fish

mkdir -p ~/.local/bin
fish_add_path -m ~/.local/bin

for file in *.fish
    if test $file = install.fish || test $file = nvim.fish
        continue
    else
        set scripts $scripts $file
    end
end

for file in $scripts
    ./$file
    echo $file
    if test $status -ne 0
        echo "Script $file failed"
        exit 1
    end
end

../stow.fish

# bat theme (also used in lazygit) is in a config file, but it needs to be recognized
bat cache --build
# git credentials in wsl, do it after stow
set wsl_file /proc/sys/fs/binfmt_misc/WSLInterop
if test -e $wsl_file then
    git config --global credential.helper "/mnt/c/Program\ Files/Git/mingw64/libexec/git-core/git-credential-wincred.exe"
end

./nvim.fish
