---
name: skill-structure
description: Frontmatter fields, naming rules, directory conventions, and progressive disclosure for Agent Skills.
---

# Skill Structure

## Contents

- [Directory Conventions](#directory-conventions)
- [SKILL.md Format](#skillmd-format)
- [Frontmatter Fields](#frontmatter-fields)
- [Name Rules](#name-rules)
- [Description Best Practices](#description-best-practices)
- [Name Conventions for Reference Files](#name-conventions-for-reference-files)
- [Pi-Specific Locations](#pi-specific-locations)
- [Progressive Disclosure](#progressive-disclosure)
- [Validation](#validation)

## Directory Conventions

```
my-skill/
├── SKILL.md          # Required: metadata + core instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation loaded on demand
├── assets/           # Optional: templates, resources
└── ...               # Any additional files or directories
```

- **SKILL.md** is the only required file. It must start with YAML frontmatter.
- **scripts/** holds self-contained, tested scripts the agent can execute via bash.
- **references/** holds documentation the agent loads on demand. Keep files focused — smaller files mean less context consumed when loaded.
- **assets/** holds templates, images, data files, schemas.

## SKILL.md Format

A `SKILL.md` file must contain YAML frontmatter followed by Markdown body:

```markdown
---
name: skill-name
description: What this skill does and when to use it.
license: Apache-2.0           # Optional
compatibility: Requires git and jq  # Optional, max 500 chars
metadata:                     # Optional, arbitrary key-value
  author: example-org
  version: "1.0"
allowed-tools: Bash(git:*) Bash(jq:*)  # Optional, experimental
---

# Skill instructions (Markdown body)

Content here. No format restrictions.
```

### Frontmatter Fields

| Field | Required | Constraints |
|-------|----------|-------------|
| `name` | Yes | Max 64 chars. Lowercase letters, numbers, hyphens. No leading/trailing hyphens, no consecutive hyphens. |
| `description` | Yes | Max 1024 chars. Non-empty. Describes what the skill does and when to use it. |
| `license` | No | License name or reference to bundled file. Keep short. |
| `compatibility` | No | Max 500 chars. Environment requirements (system packages, network access, intended product). Most skills don't need this. |
| `metadata` | No | Arbitrary string-to-string map. Use for author, version, etc. Make keys reasonably unique. |
| `allowed-tools` | No | Space-separated list of pre-approved tools. Experimental — support varies by agent. |

For broad compatibility, avoid XML tags in frontmatter values and avoid reserved brand names such as `anthropic` or `claude` in skill names.

### Name Rules

- 1-64 characters
- Only lowercase letters (`a-z`), digits (`0-9`), and hyphens (`-`) for maximum portability; some clients accept Unicode lowercase alphanumerics, but ASCII is safest.
- No leading or trailing hyphens
- No consecutive hyphens (`--`)
- The Agent Skills standard requires the name to match the parent directory. Pi does not enforce this — it allows names that differ from the directory, which is useful for shared skill directories.

**Valid:** `pdf-processing`, `data-analysis`, `code-review`
**Invalid:** `PDF-Processing`, `-pdf`, `pdf--processing`

Prefer **gerund form** (verb + -ing): `processing-pdfs`, `analyzing-spreadsheets`, `managing-databases`. Alternatives: noun phrases (`pdf-processing`) or action-oriented (`process-pdfs`). Avoid vague names (`helper`, `utils`, `tools`) and reserved words (`anthropic`, `claude`).

### Description Best Practices

The description is the **sole mechanism** for skill discovery. It carries the entire burden of triggering. Write it in **third person** (not "I can help" or "you can use this").

Include both **what** the skill does and **when** to use it. Be specific with key terms:

```yaml
# Good
description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.

# Poor
description: Helps with PDFs.
```

For optimization, see [evaluating-skills](evaluating-skills.md).

## Name Conventions for Reference Files

Use descriptive names that indicate content, not `doc1.md` or `file2.md`. Use kebab-case: `form-validation-rules.md`, `api-schema.yaml`.

## Pi-Specific Locations

Pi loads skills from (in order): `~/.pi/agent/skills/`, `~/.agents/skills/`, `.pi/skills/`, `.agents/skills/` (in cwd and ancestors). Individual `.md` files in `~/.pi/agent/skills/` and `.pi/skills/` are also discovered as skills. See the pi skills docs for full details on settings, CLI flags, and package-based skills.

## Progressive Disclosure

Structure content to match how agents load it:

1. **Metadata** (~100 tokens): `name` + `description` loaded at startup for all skills
2. **SKILL.md body** (< 500 lines / ~5000 tokens recommended): Loaded when skill activates
3. **Reference files** (as needed): Loaded only when the agent reads them

Keep `SKILL.md` body under 500 lines. Move detailed material to `references/`. Reference files should be **one level deep** from `SKILL.md` — deeply nested reference chains cause agents to preview files with `head -100` instead of reading them fully.

## Validation

Use the `skills-ref` package to validate. The package's CLI entrypoint is commonly `agentskills`:

```bash
uvx --from skills-ref agentskills validate ./my-skill
# or
pipx run --spec skills-ref agentskills validate ./my-skill
```

If your environment provides a direct `skills-ref` executable, that older wrapper may also work. Pi performs its own validation on load, warning about most violations but still loading the skill. Skills with missing descriptions are not loaded.

<!--
Source references:
- https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#skill-structure
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#naming-conventions
-->
