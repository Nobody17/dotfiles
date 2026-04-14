#!/usr/bin/env fish

mkdir -p ~/.local/bin
fish_add_path -m ~/.local/bin

# 1. Check for apt and run scripts in apt/ directory
if command -q apt
    if test -d apt
        if test -f apt/ubuntu.fish
            apt/ubuntu.fish
	end
        echo "Apt detected. Running scripts in apt/..."
        for file in apt/*.fish
            # Ensure we don't try to run the directory if it's empty/glob fails
            if test $file = apt/ubuntu.fish
                continue
            else
                fish ./$file
                if test $status -ne 0
                    echo "Script $file failed"
                    exit 1
                end
            end
        end
    end
end

if test -f ./paru.fish
    ./paru.fish
end


# 2. Collect and run fish scripts in the current directory
# Excluding install.fish and nvim.fish as per your original logic
set scripts
for file in *.fish
    if test $file = install.fish -o $file = paru.fish
        continue
    else
        set -a scripts $file
    end
end

for file in $scripts
    ./$file
    echo "Executed: $file"
    if test $status -ne 0
        echo "Script $file failed"
        exit 1
    end
end

# 3. Environment Setup
if test -f ../stow.fish
    ../stow.fish
end

# Rebuild bat cache
if command -q bat
    bat cache --build
end

# Git credentials for WSL
set wsl_file /proc/sys/fs/binfmt_misc/WSLInterop
if test -e $wsl_file
    git config --global credential.helper "/mnt/c/Program\ Files/Git/mingw64/libexec/git-core/git-credential-wincred.exe"
end

