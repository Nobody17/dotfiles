#!/usr/bin/env fish
sudo apt install curl unzip
curl -fsSL https://fnm.vercel.app/install | bash
source /home/yorunai/.config/fish/conf.d/fnm.fish

fnm install --lts
fnm install --latest
fnm use latest

corepack enable pnpm

pnpm add -g yaml-language-server
