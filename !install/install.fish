#!/usr/bin/env fish

for file in *.fish
    if test $file = install.fish
        continue
    else
        set scripts $scripts $file
    end
end

for file in $scripts
    ./$file
    if test $status -ne 0
        echo "Script $file failed"
        exit 1
    end
end

../stow.fish

# git credentials in wsl, do it after stow
set wsl_file /proc/sys/fs/binfmt_misc/WSLInterop
if test -e $wsl_file then
    git config --global credential.helper "/mnt/c/Program\ Files/Git/mingw64/libexec/git-core/git-credential-wincred.exe"
end
