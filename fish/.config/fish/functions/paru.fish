# Run paru with the mise runtimes removed from PATH.
#
# makepkg inherits the interactive PATH, where mise activation puts its own
# python, node, ruby and go in front of /usr/bin. A PKGBUILD that calls a bare
# interpreter then builds against the mise runtime instead of the system one.
# That either fails, because the pacman makedepends are only installed for the
# system interpreter, or it writes the package files into the mise prefix. Only
# the system layer belongs in a pacman package.
#
# Everything that mise does not manage stays on PATH, so rustup keeps supplying
# cargo to AUR packages that need it.

function _mise_root --description "Directory that holds the mise installs and shims"
    if test -n "$MISE_DATA_DIR"
        string trim --right --chars=/ -- "$MISE_DATA_DIR"
    else
        echo "$HOME/.local/share/mise"
    end
end

function _path_without_mise --description "Copy of PATH with all mise directories removed"
    set -l mise_root (_mise_root)
    set -l kept_directories

    for directory in $PATH
        if not string match --quiet -- "$mise_root/*" $directory
            set --append kept_directories $directory
        end
    end

    string join \n -- $kept_directories
end

function paru --description "paru with the mise runtimes removed from PATH"
    set --local --export PATH (_path_without_mise)
    command paru $argv
end
