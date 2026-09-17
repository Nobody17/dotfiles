# Generation Info

- **Source:** `/home/yorunai/programming/skill_creation/homeassistant/docs/`
- **Source type:** Local copy of Home Assistant team documentation
- **Git SHA:** Not available; source directory is not a Git worktree in this environment
- **Generated:** 2026-05-23
- **Mode:** Generated skill synthesized from documentation, not copied verbatim
- **Notes:** Core behavior is in `SKILL.md`. `references/` contains a concise pattern reference and a source-doc map; the full documentation corpus was not vendored into the skill.
- **Improvement 2026-05-23:** Clarified script `sequence:` vs automation `actions` and blueprint input-section/version gotchas from `docs/scripts.markdown` and `docs/blueprint/schema.markdown`; added output eval coverage for reusable scripts. After trigger eval failures, made the description explicitly target Home Assistant YAML/code/config, exclude hardware/UI-only/non-HA YAML near misses, and quoted the frontmatter description so the colon-heavy trigger text remains valid YAML.
