## Checks

Tests: `python3 -m unittest discover -s '!tests'` (about 40 s; on a busy machine up to 75 s, so give it a 120 s budget). `.githooks/pre-commit` checks whitespace and sh, fish, and TOML syntax of staged files.

## Agent skills

### Issue tracker

Issues and specs live as local markdown files under `.scratch/<feature>/`. See `!docs/agents/issue-tracker.md`.

### Triage labels

The five default triage roles. Each label string is the same as its role name. See `!docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` at the repo root and ADRs in `!docs/adr/`. See `!docs/agents/domain.md`.
