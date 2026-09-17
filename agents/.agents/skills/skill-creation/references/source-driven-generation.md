---
name: source-driven-generation
description: How to create or update skills from repositories, documentation, vendor skills, and other source artifacts.
---

# Source-Driven Skill Generation

Use this when the input is a documentation site, repository, upstream skill collection, runbook set, or other source corpus.

## Contents

- [Classify the source](#classify-the-source)
- [Extract agent-facing value](#extract-agent-facing-value)
- [Package generated skills](#package-generated-skills)
- [Track provenance and updates](#track-provenance-and-updates)
- [Update workflow](#update-workflow)

## Classify the source

Choose the maintenance mode before writing:

1. **Generated skill** — the project has no maintained skill. Synthesize a new skill from docs, examples, code, issues, and runbooks.
2. **Synced skill** — the project already maintains a skill. Copy it as-is, optionally rename/package it, and avoid local manual edits; contribute fixes upstream.
3. **Hand-written skill** — encode local preferences, recurring corrections, or personal/team workflow knowledge. Use real task traces as the source of truth.

## Extract agent-facing value

When reading docs or a repository:

- Focus on agent capabilities and practical usage patterns: exact commands, APIs, config snippets, failure modes, validation steps, examples, and decision points.
- Ignore user-facing introductions, marketing, basic install/get-started content, and concepts agents already know unless the project has a non-obvious convention.
- Rewrite and synthesize for agents; do not copy docs verbatim. Prefer a concise workflow + gotchas + examples over exhaustive documentation.
- Capture why a pattern is preferred when that affects agent decisions.
- Include working code or command examples when the skill teaches API/tool usage.

## Package generated skills

For multi-topic source material:

- Keep `SKILL.md` as the index and core workflow. Put one concept per `references/*.md` file.
- Organize reference files by practical categories such as `core-*`, `feature-*`, `best-practices-*`, or `advanced-*` when that makes scanning easier.
- Give each reference a short description and tell the agent when to read it from `SKILL.md`.
- Put source links in an HTML comment at the end of each generated file:

```markdown
<!--
Source references:
- https://example.com/docs/relevant-page
- https://github.com/org/repo/blob/<sha>/path/to/file
-->
```

## Track provenance and updates

For generated skills, add `GENERATION.md` when the source corpus is external or versioned:

```markdown
# Generation Info

- **Source:** `sources/project` or https://github.com/org/repo
- **Git SHA:** `abc123...`
- **Generated:** YYYY-MM-DD
- **Notes:** Optional summary of included/excluded docs
```

For synced skills, add `SYNC.md`:

```markdown
# Sync Info

- **Source:** `vendor/project/skills/skill-name`
- **Git SHA:** `abc123...`
- **Synced:** YYYY-MM-DD
- **Local changes:** None; contribute changes upstream
```

## Update workflow

1. Identify the previous source SHA from `GENERATION.md` or `SYNC.md`.
2. Diff source changes since that SHA, scoped to docs/skills paths when possible:
   ```bash
   git diff <old-sha>..HEAD -- docs/ skills/
   ```
3. Update only the affected workflow, gotchas, examples, references, and source links.
4. Re-run validation and representative evals.
5. Update `GENERATION.md` or `SYNC.md` with the new SHA and date.

<!--
Source references:
- https://github.com/antfu/skills/blob/main/AGENTS.md
- https://github.com/agentskills/agentskills/blob/main/docs/skill-creation/best-practices.mdx
- https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx
-->
