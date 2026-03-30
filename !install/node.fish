#!/usr/bin/env fish

if command -v paru > /dev/null
    paru -S --needed fnm unzip
else if command -v apt > /dev/null
    sudo apt update
    sudo apt install -y curl unzip
    curl -fsSL https://fnm.vercel.app/install | bash -s -- --skip-shell
else
    echo "Error: Neither 'paru' nor 'apt' was found."
    exit 1
end

set -l fnm_configuration_path "$HOME/.config/fish/conf.d/fnm.fish"

if not test -f $fnm_configuration_path
    if command -v fnm > /dev/null
        mkdir -p (dirname $fnm_configuration_path)
        fnm env --use-on-cd --shell fish > $fnm_configuration_path
    end
end

source $fnm_configuration_path

fnm install --lts
fnm install --latest
fnm use latest

if command -v node > /dev/null
    echo "Success: Node "(node -v)" are installed and ready."
else
    echo "Error: Installation failed."
    exit 1
end
