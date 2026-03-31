#!/usr/bin/env fish

set -l fzf_installation_directory "$HOME/.fzf"

if command -v git > /dev/null
    if test -d $fzf_installation_directory
        rm -rf $fzf_installation_directory
    end

    git clone --depth 1 https://github.com/junegunn/fzf.git $fzf_installation_directory
    
    $fzf_installation_directory/install --all
else
    echo "Error: git was found. Cannot install fzf."
    exit 1
end
