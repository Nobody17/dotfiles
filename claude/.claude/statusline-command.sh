#!/bin/bash
# Claude Code statusline styled after the user's fish/starship prompt
# (Catppuccin Mocha palette, Nerd Font icons; see ~/.config/starship.toml).
# One row: directory, git branch, model, context left, tokens in context,
# 5-hour and weekly usage limits (the latter when provided).
# Git calls skip optional locks. Fields may be absent/null early in a session.

input=$(cat)

cwd=$(jq -r '.workspace.current_dir' <<<"$input")
model=$(jq -r '.model.display_name' <<<"$input")
context_pct=$(jq -r '.context_window.remaining_percentage // empty' <<<"$input")
in_tok=$(jq -r '.context_window.total_input_tokens // empty' <<<"$input")
out_tok=$(jq -r '.context_window.total_output_tokens // empty' <<<"$input")
ctx_size=$(jq -r '.context_window.context_window_size // empty' <<<"$input")
fh_pct=$(jq -r '.rate_limits.five_hour.used_percentage // empty' <<<"$input")
fh_reset=$(jq -r '.rate_limits.five_hour.resets_at // empty' <<<"$input")
sd_pct=$(jq -r '.rate_limits.seven_day.used_percentage // empty' <<<"$input")
sd_reset=$(jq -r '.rate_limits.seven_day.resets_at // empty' <<<"$input")
dir_display=$(basename "$cwd")

# Catppuccin Mocha (truecolor ANSI)
BLUE=$'\033[38;2;137;180;250m'
MAUVE=$'\033[38;2;203;166;247m'
GREEN=$'\033[38;2;166;227;161m'
YELLOW=$'\033[38;2;249;226;175m'
RED=$'\033[38;2;243;139;168m'
PEACH=$'\033[38;2;250;179;135m'
SUBTEXT=$'\033[38;2;166;173;200m'
RESET=$'\033[0m'

# Format a token count as 12.3k / 1.2M
fmt_tokens() {
    local n=$1
    if [ "$n" -ge 1000000 ]; then awk -v n="$n" 'BEGIN{printf "%.1fM", n/1000000}'
    elif [ "$n" -ge 1000 ]; then awk -v n="$n" 'BEGIN{printf "%.1fk", n/1000}'
    else printf '%s' "$n"; fi
}

# Pick a colour for a usage percentage
pct_color() {
    local p=${1%.*}
    if [ "$p" -ge 80 ]; then printf '%s' "$RED"
    elif [ "$p" -ge 50 ]; then printf '%s' "$YELLOW"
    else printf '%s' "$GREEN"; fi
}

# Format a reset epoch: HH:MM if today, else "Mon HH:MM"
fmt_reset() {
    local ts=$1
    if [ "$(date -r "$ts" +%Y%m%d)" = "$(date +%Y%m%d)" ]; then date -r "$ts" +%H:%M
    else date -r "$ts" +"%a %H:%M"; fi
}

git_segment=""
if git -C "$cwd" --no-optional-locks rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    branch=$(git -C "$cwd" --no-optional-locks branch --show-current 2>/dev/null)
    [ -n "$branch" ] && git_segment=" ${GREEN} ${branch}${RESET}"
fi

context_segment=""
[ -n "$context_pct" ] && context_segment=" ${SUBTEXT}(${context_pct}% left)${RESET}"

line1="${BLUE} ${dir_display}${RESET}${git_segment} ${MAUVE}${model}${RESET}${context_segment}"

# Tokens and limits
parts=()
if [ -n "$in_tok" ] && [ -n "$out_tok" ]; then
    tok_seg="${PEACH}󰊤 $(fmt_tokens $((in_tok + out_tok)))"
    [ -n "$ctx_size" ] && tok_seg+="${SUBTEXT}/$(fmt_tokens "$ctx_size")"
    parts+=("${tok_seg}${RESET}")
fi
if [ -n "$fh_pct" ]; then
    seg="$(pct_color "$fh_pct")󰥔 5h ${fh_pct%.*}%${RESET}"
    [ -n "$fh_reset" ] && seg+=" ${SUBTEXT}↻ $(fmt_reset "$fh_reset")${RESET}"
    parts+=("$seg")
fi
if [ -n "$sd_pct" ]; then
    seg="$(pct_color "$sd_pct")󰃭 7d ${sd_pct%.*}%${RESET}"
    [ -n "$sd_reset" ] && seg+=" ${SUBTEXT}↻ $(fmt_reset "$sd_reset")${RESET}"
    parts+=("$seg")
fi

line="$line1"
for p in "${parts[@]}"; do
    line+="  ${SUBTEXT}·${RESET}  $p"
done
printf '%s\n' "$line"
