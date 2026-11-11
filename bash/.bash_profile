# A login bash reads only this file, not ~/.bashrc. Claude Code makes its
# shell snapshot with a login bash, so all setup lives in ~/.bashrc.
if [ -f "$HOME/.bashrc" ]; then
    . "$HOME/.bashrc"
fi
