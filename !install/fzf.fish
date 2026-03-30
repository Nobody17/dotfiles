#!/usr/bin/env fish

set -l fzf_installation_directory "$HOME/.fzf"

if command -v paru > /dev/null
    echo "Paru detected. Installing fzf via AUR..."
    paru -S --needed fzf


else if command -v git > /dev/null
    echo "Paru not found. Falling back to manual git installation..."
    
    if test -d $fzf_installation_directory
        rm -rf $fzf_installation_directory
    end

    git clone --depth 1 https://github.com/junegunn/fzf.git $fzf_installation_directory
    
    $fzf_installation_directory/install --all
else
    echo "Error: Neither 'paru' nor 'git' was found. Cannot install fzf."
    exit 1
end

echo "fzf installation logic complete."
