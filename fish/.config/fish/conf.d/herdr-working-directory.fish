# Keep Herdr's saved directory current even if the shell exits before its server.
if not status is-interactive; or test "$HERDR_ENV" != 1
    return
end

function herdr_report_working_directory --on-variable PWD --on-event fish_prompt
    # Encode spaces and control characters. Write to the terminal, not command output.
    printf '\e]7;file://localhost%s\e\\' (string escape --style=url -- "$PWD") >/dev/tty
end

herdr_report_working_directory
