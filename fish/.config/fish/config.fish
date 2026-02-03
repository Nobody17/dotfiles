function y
    set tmp (mktemp -t "yazi-cwd.XXXXXX")
    yazi $argv --cwd-file="$tmp"
    if set cwd (command cat -- "$tmp"); and [ -n "$cwd" ]; and [ "$cwd" != "$PWD" ]
        builtin cd -- "$cwd"
    end
    rm -f -- "$tmp"
end

# Set up fzf key bindings
fzf --fish | source
if status is-interactive
  zoxide init fish | source
end
starship init fish | source
enable_transience

set -gx ERL_AFLAGS "-kernel shell_history enabled"
set -gxa ASDF_DATA_DIR "/home/yorunai/.asdf"
fish_add_path "/home/yorunai/.asdf/shims"
fish_add_path "/home/yorunai/bin"

pyenv init - | source

#abbreviations
abbr g lazygit
abbr lzd lazydocker
abbr l eza -lah --git --git-repos --group-directories-first
abbr lts eza -lah --git --git-repos --group-directories-first --total-size
abbr n nvim
alias get_idf=". $HOME/esp/esp-idf/export.fish"

#WSL
# set -gxa SSH_SK_HELPER "/mnt/c/bin/SSH/ssh-sk-helper.exe"
#Linux
set -gxa SSH_ASKPASS "/usr/bin/ssh-askpass"

#path
fish_add_path "/home/yorunai/Programming/software/android-studio/bin/"
fish_add_path "/home/yorunai/Programming/software/platform-tools/"
fish_add_path "/opt/nvim/bin"
fish_add_path "/home/yorunai/.local/share/nvim/mason/bin"
fish_add_path "/usr/local/go/bin"
fish_add_path "/home/yorunai/go/bin"
fish_add_path "/home/yorunai/.config/herd-lite/bin"
set -gxa PHP_INI_SCAN_DIR "/home/yorunai/.config/herd-lite/bin"


set PATH $PATH /home/yorunai/.local/bin

# >>> mamba initialize >>>
# !! Contents within this block are managed by 'micromamba shell init' !!
set -gx MAMBA_EXE "/home/yorunai/.local/bin/micromamba"
set -gx MAMBA_ROOT_PREFIX "/home/yorunai/.local/share/mamba"
$MAMBA_EXE shell hook --shell fish --root-prefix $MAMBA_ROOT_PREFIX | source
# <<< mamba initialize <<<

# Prefer custom FFmpeg (xHE-AAC via libfdk_aac)
set -e -g fish_user_paths            # remove any shadowing global
fish_add_path -U --prepend /opt/ffmpeg/bin

