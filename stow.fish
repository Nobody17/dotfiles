#!/usr/bin/env fish

# stow.fish links each package folder of this repository into your home folder.
#
# A package is a top-level folder of this repository. A folder whose name starts
# with "!" or "." is not a package. The "!install" folder holds the bootstrap
# scripts, and the "!" prefix keeps those scripts out of your home folder.
# Keep that prefix.
#
# The script builds the package list itself. It does not trust a stow ignore
# file for that job. Use "--list" to see the list.
#
# Use "./stow.fish --help" for the options.

set --local repository_root (path resolve (path dirname (status filename)))

# Packages that must get one symlink for each file, and never one symlink for
# the whole folder.
#
# stow folds a whole folder into a single symlink when the target folder does
# not exist yet. The folder in your home is then the folder in this repository,
# so every file that the program writes lands inside this git repository.
# ~/.pi shows that effect today.
#
# --no-folding stops the fold. Each package below owns a folder that its
# program writes into:
#   claude  writes .credentials.json, sessions/ and history.jsonl
#   btop    writes btop.conf again when you quit, and makes themes/
#   micro   writes settings.json again, and makes colorschemes/ and plug/
#   ghostty reads hypr-background-opacity.conf, which monitors.lua writes
#   hypr    keeps monitors.lua, devices.lua and plugins/ local, because they
#           describe the hardware of one machine
set --local no_folding_packages claude btop micro ghostty hypr

function print_usage
    echo "Usage: stow.fish [options] [package ...]"
    echo
    echo "Links each package folder of this repository into your home folder."
    echo "The script uses every package it finds if you name none."
    echo
    echo "Options:"
    echo "  -n, --dry-run    Show the planned changes. Change nothing."
    echo "  -D, --delete     Remove the symlinks. Do not make them."
    echo "  -l, --list       Show the package list. Then stop."
    echo "      --no-adopt   Never move a local file into this repository."
    echo "  -y, --yes        Answer yes to the question about the local files."
    echo "  -h, --help       Show this text."
    echo
    echo "About --adopt:"
    echo "  A normal run gives --adopt to stow. If your home folder holds a real"
    echo "  file where a symlink must go, stow moves that file into this"
    echo "  repository, then makes a symlink to it. Your machine keeps the same"
    echo "  content, but the repository copy changes. The script therefore needs"
    echo "  a clean repository first. It then shows each moved file, and it asks"
    echo "  you if the repository version must come back."
    echo
    echo "  Use --no-adopt to stop the move. stow then stops at the first clash"
    echo "  and changes nothing. --no-adopt also runs with a dirty repository."
end

function repository_has_changes --description 'True if a tracked file differs from the last commit'
    git status --porcelain --untracked-files=no | string length --quiet
end

# ------------------------------------------------------------------- arguments

argparse --name=stow.fish h/help n/dry-run D/delete l/list y/yes no-adopt -- $argv
or begin
    echo
    print_usage
    exit 2
end

if set --query _flag_help
    print_usage
    exit 0
end

# ------------------------------------------------------------- repository root

if not test -d "$repository_root"
    echo "❌ Stop: the script cannot find its own repository folder."
    echo "   It looked at: $repository_root"
    exit 1
end

if not cd "$repository_root"
    echo "❌ Stop: the script cannot enter $repository_root."
    echo "   Check the permissions of that folder."
    exit 1
end

if not set --query HOME; or not test -d "$HOME"
    echo "❌ Stop: HOME does not point to a folder that exists."
    exit 1
end

# --------------------------------------------------------------- tool checks

if not command --query stow
    echo "❌ Stop: GNU Stow is not installed, so the script can link nothing."
    if command --query paru
        echo "   Install it:  paru -S stow"
    else if command --query pacman
        echo "   Install it:  sudo pacman -S stow"
    else
        echo "   Install it:  fish '$repository_root/!install/apt/stow.fish'"
    end
    exit 1
end

if not command --query git
    echo "❌ Stop: git is not installed."
    echo "   The script needs git to keep your files safe, so it stops here."
    exit 1
end

if not git rev-parse --is-inside-work-tree >/dev/null 2>&1
    echo "❌ Stop: $repository_root is not inside a git repository."
    echo "   The script uses git to undo an unwanted overwrite."
    echo "   Clone the dotfiles repository, then run the script from the clone."
    exit 1
end

set --local git_root (path resolve (git rev-parse --show-toplevel))
if test "$git_root" != "$repository_root"
    echo "❌ Stop: the git root is not the folder of this script."
    echo "   Script folder: $repository_root"
    echo "   Git root:      $git_root"
    echo "   A restore would then touch files outside the dotfiles."
    exit 1
end

# --------------------------------------------------------- package discovery

set --local available_packages
set --local non_packages

for entry in */
    set --local candidate (string trim --right --chars=/ -- $entry)
    if string match --quiet -- '!*' $candidate; or string match --quiet -- '.*' $candidate
        set --append non_packages $candidate
    else
        set --append available_packages $candidate
    end
end

if set --query _flag_list
    echo "Packages in $repository_root:"
    for name in $available_packages
        if contains -- $name $no_folding_packages
            echo "  • $name   (one symlink for each file)"
        else
            echo "  • $name"
        end
    end
    if test (count $non_packages) -gt 0
        echo
        echo "Not packages, so never linked into your home folder:"
        for name in $non_packages
            echo "  • $name"
        end
    end
    exit 0
end

set --local selected_packages $available_packages

if test (count $argv) -gt 0
    set selected_packages
    for raw_name in $argv
        set --local name (string trim --right --chars=/ -- $raw_name)
        if not contains -- $name $available_packages
            echo "❌ Stop: \"$name\" is not a package of this repository."
            echo "   See the list:  $repository_root/stow.fish --list"
            exit 1
        end
        contains -- $name $selected_packages; or set --append selected_packages $name
    end
end

if test (count $selected_packages) -eq 0
    echo "❌ Stop: the script found no package in $repository_root."
    exit 1
end

# ----------------------------------------------------------------- stow flags

set --local stow_arguments --verbose --dir=$repository_root --target=$HOME
set --local adopt_is_active 0

if set --query _flag_delete
    set --append stow_arguments --delete
else
    set --append stow_arguments --restow
    if not set --query _flag_no_adopt
        # A dry run keeps --adopt, so the plan shows exactly what a normal run
        # does. Each move then appears as an "MV:" line.
        set --append stow_arguments --adopt
        set adopt_is_active 1
    end
end

if set --query _flag_dry_run
    set --append stow_arguments --simulate
end

# ------------------------------------------------------- clean repository check

# Only --adopt can overwrite a file of this repository, so only --adopt needs a
# clean repository. An untracked file is safe, because --adopt writes over a
# package file, and a package file that git tracks shows up as a change.
if test $adopt_is_active -eq 1; and not set --query _flag_dry_run; and repository_has_changes
    echo "❌ Stop: this repository has changes in tracked files."
    echo "   stow --adopt can write over a file here, so the repository must be clean."
    echo "--------------------------------------------------------------------------------"
    git status --short --untracked-files=no
    echo "--------------------------------------------------------------------------------"
    echo "Do one of these, then run the script again:"
    echo "  See the changes:  git -C $repository_root diff"
    echo "  Keep them:        git -C $repository_root commit -a -m \"update config\""
    echo "  Park them:        git -C $repository_root stash push"
    echo "  Remove them:      git -C $repository_root restore --worktree --staged -- :/"
    echo
    echo "Or link now and leave this repository as it is:"
    echo "  $repository_root/stow.fish --no-adopt"
    exit 1
end

# ---------------------------------------------------------------------- action

set --local folding_packages
set --local unfolded_packages

for name in $selected_packages
    if contains -- $name $no_folding_packages
        set --append unfolded_packages $name
    else
        set --append folding_packages $name
    end
end

set --local action_name Linking
if set --query _flag_delete
    set action_name Unlinking
end
if set --query _flag_dry_run
    set action_name "$action_name (dry run)"
end

echo "📦 $action_name "(count $selected_packages)" package(s) into $HOME"
echo "   "(string join ", " $selected_packages)
echo "--------------------------------------------------------------------------------"

set --local stow_output
set --local worst_exit_status 0

# stow has no option that turns folding off for one package only, so the
# script calls stow a second time for the packages that must stay unfolded.
# stow also does not accept "--", so the package names follow the flags.
if test (count $folding_packages) -gt 0
    set --local output (stow $stow_arguments $folding_packages 2>&1)
    set --local exit_status $status
    test $exit_status -gt $worst_exit_status; and set worst_exit_status $exit_status
    set --append stow_output $output
    printf '%s\n' $output
end

if test (count $unfolded_packages) -gt 0
    set --local output (stow $stow_arguments --no-folding $unfolded_packages 2>&1)
    set --local exit_status $status
    test $exit_status -gt $worst_exit_status; and set worst_exit_status $exit_status
    set --append stow_output $output
    printf '%s\n' $output
end

echo "--------------------------------------------------------------------------------"

set --local moved_files (printf '%s\n' $stow_output | string match --regex --groups-only '^MV: (.*) ->')

# ------------------------------------------------------------------- dry run

if set --query _flag_dry_run
    echo
    if test $worst_exit_status -ne 0
        echo "⚠️  The dry run changed nothing, but stow reported a problem above."
        exit $worst_exit_status
    end
    if test (count $moved_files) -gt 0
        echo "⚠️  The dry run changed nothing. A normal run moves "(count $moved_files)" file(s)"
        echo "   out of your home folder and into this repository:"
        for file in $moved_files
            echo "     • $file"
        end
        echo "   Your machine keeps the same content, but the repository copy changes."
        echo "   The normal run shows each moved file again, and it asks you what to keep."
        echo "   Use --no-adopt to stop instead of moving anything."
    else
        echo "✅ The dry run changed nothing. stow found no clash."
    end
    exit 0
end

if test $worst_exit_status -ne 0
    echo
    echo "❌ stow stopped with status $worst_exit_status. Read the messages above."
    if set --query _flag_no_adopt
        echo "   --no-adopt was given, so stow moved no local file."
        echo "   Move the named files away yourself, or run without --no-adopt."
    end
    echo "   See the plan and change nothing:  $repository_root/stow.fish --dry-run"
    exit $worst_exit_status
end

# --------------------------------------------------------------- after adopt

if set --query _flag_delete
    echo
    echo "✅ Unlinked. Each file stays in this repository."
    echo "   Link them again:  $repository_root/stow.fish"
else if test $adopt_is_active -eq 0
    echo
    echo "✅ Each package is linked. No file moved, because --no-adopt was given."
else if not repository_has_changes
    echo
    echo "✅ Each package is linked. stow moved no local file."
else
    echo
    echo "⚠️  stow moved these files out of your home folder and into this repository:"
    echo "--------------------------------------------------------------------------------"
    git status --short --untracked-files=no
    echo "--------------------------------------------------------------------------------"
    echo "Your home folder points to them now, so this machine reads the same content."
    echo

    set --local answer ""
    if set --query _flag_yes
        set answer y
        echo "--yes was given, so the repository versions win."
    else if not isatty stdin
        echo "There is no terminal for a question, so the script restores nothing."
    else
        while true
            read --local --prompt-str "Use the repository versions instead? [y/N/d=see the diff]: " answer
            or begin
                set answer ""
                break
            end
            if string match --quiet --regex --ignore-case '^d(iff)?$' -- "$answer"
                echo
                git --no-pager diff --stat
                echo
                git --no-pager diff
                echo
                continue
            end
            break
        end
    end

    if string match --quiet --regex --ignore-case '^y(es)?$' -- "$answer"
        # The check above proved the repository was clean, so each change here
        # comes from --adopt. ":/" covers the whole repository, not only the
        # current folder.
        git restore --worktree --staged -- :/
        echo "🔄 The repository versions are back in place."
    else
        echo "❌ The script restored nothing. The moved files stay here as changes."
        echo
        echo "   Read this before the next run:"
        echo "   A normal run stops at the clean repository check until you clear them."
        echo "   Do one of these:"
        echo "     Keep them:    git -C $repository_root commit -a -m \"adopt local config\""
        echo "     Park them:    git -C $repository_root stash push"
        echo "     Remove them:  git -C $repository_root restore --worktree --staged -- :/"
        echo "   Or link again without the check:  $repository_root/stow.fish --no-adopt"
    end
end

# -------------------------------------------------------------- next steps

echo
echo "🔁 Next steps on this machine:"
echo "  • The script runs in its own shell, so it cannot change the shell you"
echo "    typed in. Load the new fish configuration:"
echo "      exec fish"

if set --query _flag_delete
    if set --query HYPRLAND_INSTANCE_SIGNATURE; and command --query hyprctl
        echo "  • Hyprland still uses the old configuration. Reload it when you are ready:"
        echo "      hyprctl reload"
    end
    exit 0
end

if command --query bat; and test -d $HOME/.config/bat
    if bat cache --build >/dev/null 2>&1
        echo "  • The script rebuilt the bat theme cache."
    else
        echo "  • ⚠️  \"bat cache --build\" failed. Run it yourself to see the error."
    end
end

if command --query mise; and test -f $HOME/.config/mise/config.toml
    echo "  • The mise configuration can list new tools. Install them:"
    echo "      mise install"
end

# ghostty reloads on SIGUSR2. Every other signal makes it crash, so name the
# signal and never send a number. This block stays on Linux: macOS pkill knows
# neither --signal nor --exact, and the macOS app reloads with cmd+shift+,
if test (uname) = Linux; and command --query ghostty; and pgrep --exact ghostty >/dev/null 2>&1
    if pkill --signal SIGUSR2 --exact ghostty >/dev/null 2>&1
        echo "  • The script told ghostty to read its configuration again."
    end
end

if set --query HYPRLAND_INSTANCE_SIGNATURE; and command --query hyprctl; and test -d $HOME/.config/hypr
    if hyprctl reload >/dev/null 2>&1
        echo "  • The script reloaded the Hyprland configuration."
    else
        echo "  • ⚠️  \"hyprctl reload\" failed. Run it yourself to see the error."
    end
end

# ------------------------------------------------------------- pi advisory

if contains -- pi $selected_packages; and test -L $HOME/.pi
    echo
    echo "ℹ️  About the pi package:"
    echo "   ~/.pi is one symlink to $repository_root/pi/.pi. stow cannot hide a"
    echo "   single file inside a folder that it linked as a whole, so"
    echo "   pi/.stow-local-ignore has no effect on this machine."
    echo "   Live pi data therefore sits inside this git repository: auth.json,"
    echo "   settings.json, trust.json, models.json, pi-debug.log,"
    echo "   run-history.jsonl, sessions/ and two node_modules/ folders."
    echo "   Only .gitignore keeps that data out of your commits. Check it:"
    echo "     git -C $repository_root status --short --untracked-files=all -- pi"
    echo "   That command must print nothing."
end
