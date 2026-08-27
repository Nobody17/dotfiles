function lazygit --description 'lazygit with a side panel of constant column width'
    # lazygit only knows a fixed fraction of the window, so the fraction is
    # calculated at start: ~60 columns on a 4K full screen window (0.15) and
    # the same ~60 columns on a half screen window (0.30).
    set --local target_columns 60
    set --local minimum_fraction 0.15
    set --local maximum_fraction 0.30

    set --local terminal_columns (tput cols 2>/dev/null)
    if not string match --quiet --regex '^[0-9]+$' -- "$terminal_columns"
        command lazygit $argv
        return
    end
    if test "$terminal_columns" -lt 1
        command lazygit $argv
        return
    end

    set --local config_home $XDG_CONFIG_HOME
    if test -z "$config_home"
        set config_home $HOME/.config
    end

    set --local config_files $LG_CONFIG_FILE
    if test -z "$config_files"
        set config_files $config_home/lazygit/config.yml
    end
    if not test -f (string split --fields 1 , -- $config_files)
        command lazygit $argv
        return
    end

    set --local runtime_directory $XDG_RUNTIME_DIR
    if test -z "$runtime_directory"
        set runtime_directory (dirname (mktemp --dry-run))
    end

    set --local overlay_file $runtime_directory/lazygit-side-panel-width.yml
    set --local side_panel_width (math --scale=4 "max($minimum_fraction, min($maximum_fraction, $target_columns / $terminal_columns))")

    printf 'gui:\n  sidePanelWidth: %s\n' $side_panel_width >$overlay_file
    or begin
        command lazygit $argv
        return
    end

    command lazygit --use-config-file "$config_files,$overlay_file" $argv
end
