---
name: writing-instructions
description: Patterns and guidelines for writing effective skill instructions.
---

# Writing Instructions

## Contents

- [Gotchas Sections](#gotchas-sections)
- [Checklists for Multi-Step Workflows](#checklists-for-multi-step-workflows)
- [Validation Loops](#validation-loops)
- [Plan-Validate-Execute](#plan-validate-execute)
- [Templates for Output Format](#templates-for-output-format)
- [Input/output examples](#inputoutput-examples)
- [Progressive Disclosure Design](#progressive-disclosure-design)
- [Calibrating Control](#calibrating-control)
- [Content Guidelines](#content-guidelines)
- [Anti-Patterns](#anti-patterns)
- [Starting from Real Expertise](#starting-from-real-expertise)

## Gotchas Sections

The highest-value content in many skills. Gotchas are environment-specific facts that defy reasonable assumptions — concrete corrections to mistakes the agent will make without being told:

```markdown
## Gotchas

- The `users` table uses soft deletes. Queries must include
  `WHERE deleted_at IS NULL` or results will include deactivated accounts.
- The user ID is `user_id` in the database, `uid` in the auth service,
  and `accountId` in the billing API. All three refer to the same value.
- The `/health` endpoint returns 200 even when the database is down.
  Use `/ready` to check full service health.
```

Keep gotchas in `SKILL.md` where the agent reads them before encountering the situation. When an agent makes a mistake you have to correct, add the correction to gotchas. This is one of the most direct ways to improve a skill iteratively.

## Checklists for Multi-Step Workflows

An explicit checklist helps the agent track progress and avoid skipping steps:

```markdown
## Form processing workflow

Progress:
- [ ] Step 1: Analyze the form (`scripts/analyze_form.py`)
- [ ] Step 2: Create field mapping (edit `fields.json`)
- [ ] Step 3: Validate mapping (`scripts/validate_fields.py`)
- [ ] Step 4: Fill the form (`scripts/fill_form.py`)
- [ ] Step 5: Verify output (`scripts/verify_output.py`)
```

## Validation Loops

Instruct the agent to validate its own work before moving on:

```markdown
## Editing workflow

1. Make your edits
2. Run validation: `python scripts/validate.py output/`
3. If validation fails:
   - Review the error message
   - Fix the issues
   - Run validation again
4. Only proceed when validation passes
```

A reference document can serve as the "validator" — instruct the agent to check work against it before finalizing. This pattern greatly improves output quality for any task with verifiable correctness criteria.

## Plan-Validate-Execute

For batch or destructive operations, have the agent create an intermediate plan, validate it, then execute:

```markdown
## PDF form filling

1. Extract form fields: `scripts/analyze_form.py input.pdf` → `form_fields.json`
2. Create `field_values.json` mapping each field to its intended value
3. Validate: `scripts/validate_fields.py form_fields.json field_values.json`
4. If validation fails, revise and re-validate
5. Fill: `scripts/fill_form.py input.pdf field_values.json output.pdf`
```

The key is step 3: a validation script that checks the plan against a source of truth. Error messages should be specific — e.g., "Field 'signature_date' not found. Available fields: customer_name, order_total, signature_date_signed" — to give the agent enough information to self-correct.

## Templates for Output Format

When you need the agent to produce output in a specific format, provide a template. Agents pattern-match well against concrete structures:

````markdown
## Report structure

Use this template, adapting sections as needed:

```markdown
# [Analysis Title]

## Executive summary
[One-paragraph overview of key findings]

## Key findings
- Finding 1 with supporting data
- Finding 2 with supporting data

## Recommendations
1. Specific actionable recommendation
2. Specific actionable recommendation
```
````

Short templates can live inline in `SKILL.md`. Longer templates or templates only needed in certain cases go in `assets/` and are referenced from `SKILL.md`.

## Input/output examples

Use examples when output quality depends on style, format, or judgment. Prefer realistic input/output pairs over abstract rules:

```markdown
## Example

User asks: "Summarize this incident for leadership."
Output shape:
- 2-sentence impact summary
- Customer-visible symptoms
- Timeline with UTC timestamps
- Follow-ups with owner and due date
```

Examples should demonstrate the preferred pattern and the boundary conditions that are easy to miss. Avoid stuffing the skill with many near-duplicate examples; keep only examples that change behavior.

## Progressive Disclosure Design

### Keep SKILL.md under 500 lines

Move detailed reference material to separate files. Tell the agent **when** to load each file — "Read `references/api-errors.md` if the API returns a non-200 status code" is more useful than "see references/ for details."

### Structure longer reference files with table of contents

For reference files longer than 100 lines, include a table of contents at the top. This ensures the agent can see the full scope even when previewing with partial reads:

```markdown
## Contents

- [Schema Overview](#schema-overview)
- [Table Definitions](#table-definitions)
- [Query Patterns](#query-patterns)
- [Common Errors](#common-errors)
```

### One level deep

All reference files should link directly from `SKILL.md`. Avoid chains like `SKILL.md → reference.md → sub-reference.md` — agents may use `head -100` to preview nested files instead of reading them fully.

## Calibrating Control

### Match specificity to fragility

**High freedom** — multiple approaches valid, task tolerates variation:
```markdown
## Code review process

1. Check all database queries for SQL injection (use parameterized queries)
2. Verify authentication checks on every endpoint
3. Look for race conditions in concurrent code paths
4. Confirm error messages don't leak internal details
```

**Low freedom** — operations fragile, consistency critical:
````markdown
## Database migration

Run exactly this sequence:
```bash
python scripts/migrate.py --verify --backup
```
Do not modify the command or add additional flags.
````

Most skills mix both. Calibrate each part independently.

### Explain why, not just what

Reasoning-based instructions work better than rigid directives. "Do X because Y tends to cause Z" beats "ALWAYS do X, NEVER do Y." Agents follow instructions more reliably when they understand the purpose.

## Content Guidelines

### Avoid time-sensitive information

Don't embed version numbers or dates that will become wrong. If historical context is needed, use an "old patterns" section:

```markdown
## Old patterns (pre-v2)

Prior to v2, the API used snake_case. Some endpoints still accept it.
```

### Use consistent terminology

Pick one term and stick with it throughout. "API endpoint" everywhere, not mixed with "URL", "API route", "path". "Field" everywhere, not mixed with "box", "element", "control".

### File paths: Linux-style forward slashes only

Target Linux skill environments by default. Always use forward slashes: `scripts/helper.py`, `reference/guide.md`. Do not include Windows/PowerShell path variants unless the user explicitly asks for cross-platform support.

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| Deeply nested references | Agent previews with `head -100`, misses content | One level deep from SKILL.md |
| Too many options presented equally | Agent wastes turns trying each | Pick a default, mention alternatives briefly |
| Exhaustive documentation | Agent struggles to extract what's relevant | Concise, stepwise guidance with a working example |
| Explaining basics | Wastes tokens | Assume the agent knows what a PDF/HTTP/DB migration is |
| Backslash paths | Break on Linux | Always use Linux-style forward slashes |

## Starting from Real Expertise

### Extract from a hands-on task

Complete a real task in conversation with an agent, providing context, corrections, and preferences. Then extract the reusable pattern. Pay attention to:

- **Steps that worked** — the sequence that led to success
- **Corrections you made** — where you steered the agent (e.g., "use library X instead of Y")
- **Input/output formats** — what data looked like going in and coming out
- **Context you provided** — project-specific facts the agent didn't already know

### Synthesize from existing project artifacts

Feed project-specific material into an LLM and ask it to synthesize a skill:
- Internal documentation, runbooks, style guides
- API specifications, schemas, configuration files
- Code review comments and issue trackers (captures recurring concerns)
- Version control history (reveals patterns through what actually changed)
- Real-world failure cases and their resolutions

Project-specific material (your team's incident reports, schemas, failure modes) produces far better skills than generic references.

<!--
Source references:
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- https://github.com/agentskills/agentskills/blob/main/docs/skill-creation/best-practices.mdx
- https://github.com/antfu/skills/blob/main/AGENTS.md
-->
