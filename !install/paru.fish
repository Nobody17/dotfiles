if type -q pacman
    echo "Arch-based system detected. Proceeding..."
else
    echo "Error: pacman not found. This script (paru installation) requires an Arch-based distribution."
    exit 1
end

sudo pacman -S --needed base-devel git
git clone https://aur.archlinux.org/paru.git
cd paru
makepkg -si


paru --needed cmake cpio meson
paru --needed base-devel asdf-vm ncurses glu mesa wxwidgets-gtk3 libpng libssh unixodbc libxslt fop unzip
paru --needed pyenv
paru --needed go yq taplo-cli
paru --needed git-delta lazygit lazydocker
paru --needed eza zoxide ripgrep fd fzf
paru --needed starship stow
