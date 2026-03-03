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
# 1. Enable shell history for IEx
set -gx ERL_AFLAGS "-kernel shell_history enabled"

# 2. Define ASDF Data Directory (Standard path)
set -gx ASDF_DATA_DIR "$HOME/.asdf"

# 3. Add shims and asdf bin to path
# Note: It's better to add the bin folder too so the 'asdf' command itself is found
fish_add_path "$ASDF_DATA_DIR/bin"
fish_add_path "$ASDF_DATA_DIR/shims"
fish_add_path "$HOME/bin"

# 4. Source asdf (Standard way for Fish)
if test -f "$ASDF_DATA_DIR/asdf.fish"
    source "$ASDF_DATA_DIR/asdf.fish"
end

pyenv init - | source

#abbreviations
abbr g lazygit
abbr lzd lazydocker
abbr l eza -lah --git --git-repos --group-directories-first
abbr lts eza -lah --git --git-repos --group-directories-first --total-size
abbr n nvim
alias get_idf=". $HOME/esp/esp-idf/export.fish"

#WSL
#set -gxa SSH_SK_HELPER "/mnt/c/bin/SSH/ssh-sk-helper.exe"
#Linux
#set -gxa SSH_ASKPASS "/usr/bin/ssh-askpass"

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

# Prefer custom FFmpeg (xHE-AAC via libfdk_aac)
set -e -g fish_user_paths            # remove any shadowing global
fish_add_path -U --prepend /opt/ffmpeg/bin

