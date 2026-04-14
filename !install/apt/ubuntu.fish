#!/usr/bin/env fish
sudo apt update
sudo apt install build-essential libreadline-dev 
sudo apt install git curl unzip xclip
sudo apt install lua5.1 liblua5.1-dev
sudo apt install bat
sudo apt install sqlite3
sudo apt install perl latexmk
sudo apt install gettext
sudo apt install zathura
mkdir -p ~/.local/bin
if not test e ~/.local/bin/bat
	ln -s /usr/bin/batcat ~/.local/bin/bat
end
