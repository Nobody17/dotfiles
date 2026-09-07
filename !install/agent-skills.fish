#!/usr/bin/env fish

# Third-party agent skills come from their sources, not from this repo.
# Both installers write into ~/.agents/skills, the folder that Codex and pi
# read themselves. Claude Code reads only ~/.claude/skills, so the skills.sh
# installer also puts one symlink per skill there.
#
# impeccable is installed for Codex only. Codex and pi share that copy. Claude
# Code gets impeccable from the impeccable plugin, which also carries the
# design hooks and the subagents. A second copy shows the skill twice.
#
# Needs npx, so mise.fish must have run first.
#
# Later updates:
#   npx skills@latest update -g
#   npx impeccable update

if not command -q npx
    echo "Error: npx was not found. Run mise.fish first."
    exit 1
end

# The curated set that the Claude Code plugin "mattpocock-skills" ships.
# The installer needs one --skill flag per name.
set --local matt_pocock_skills \
    ask-matt code-review codebase-design diagnosing-bugs domain-modeling \
    grill-with-docs implement improve-codebase-architecture prototype research \
    resolving-merge-conflicts setup-matt-pocock-skills tdd to-spec to-tickets \
    triage wayfinder wizard grill-me grilling handoff teach to-questionnaire \
    wait-what writing-for-agents

set --local skill_flags
for skill_name in $matt_pocock_skills
    set --append skill_flags --skill $skill_name
end

echo "==> Matt Pocock skills -> ~/.agents/skills (+ links in ~/.claude/skills)"
npx --yes skills@latest add mattpocock/skills --global \
    --agent codex --agent claude-code $skill_flags --yes
or exit 1

echo "==> impeccable -> ~/.agents/skills/impeccable"
npx --yes impeccable@latest install --scope=global --providers=codex --yes
or exit 1

set --local shared_skill_count (count ~/.agents/skills/*/)
set --local claude_link_count (count (path filter --type link ~/.claude/skills/*))
echo "Success: $shared_skill_count skills in ~/.agents/skills, $claude_link_count links in ~/.claude/skills."
