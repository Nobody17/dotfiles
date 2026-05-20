#!/usr/bin/env fish

function fail
    echo "Error: $argv" >&2
    exit 1
end

# Install dependencies
if command -v paru > /dev/null
    paru -S --needed fnm unzip || fail "Failed to install packages with paru."
else if command -v apt > /dev/null
    sudo apt update || fail "apt update failed."
    sudo apt install -y curl unzip || fail "Failed to install packages with apt."

    if not command -v fnm > /dev/null
        curl -fsSL https://fnm.vercel.app/install | bash -s -- --skip-shell \
            || fail "Failed to install fnm."
    end
else
    fail "Neither 'paru' nor 'apt' was found."
end

set -l fnm_configuration_path "$HOME/.config/fish/conf.d/fnm.fish"

# Generate fish config for fnm
if not test -f "$fnm_configuration_path"
    if command -v fnm > /dev/null
        mkdir -p (dirname "$fnm_configuration_path")
        fnm env --use-on-cd --shell fish > "$fnm_configuration_path"
    else
        fail "fnm was not found after installation."
    end
end

# Load fnm into current shell
if test -f "$fnm_configuration_path"
    source "$fnm_configuration_path"
else
    fail "fnm fish configuration was not created."
end

# Install and use Node LTS
fnm install --lts || fail "Failed to install Node LTS."
fnm default lts-latest || fail "Failed to set Node LTS as default."
fnm use lts-latest || fail "Failed to use Node LTS."

# Enable Corepack / pnpm
if command -v corepack > /dev/null
    corepack enable || fail "Failed to enable corepack."
    corepack prepare pnpm@latest --activate || fail "Failed to activate pnpm."
else
    fail "corepack not found."
end

# Generate pnpm fish completions
if command -v pnpm > /dev/null
    set -l completions_dir "$HOME/.config/fish/completions"
    mkdir -p "$completions_dir"
    pnpm completion fish > "$completions_dir/pnpm.fish"
else
    fail "pnpm not found."
end

if command -v node > /dev/null
    echo "Success: Node "(node -v)" is installed and ready."
    echo "Success: pnpm "(pnpm -v)" is installed and ready."
else
    fail "Node installation failed."
end
