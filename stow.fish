#!/usr/bin/env fish

rm -rf $HOME/.config/fish
stow --verbose --target=$HOME --restow */
