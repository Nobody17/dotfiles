---
name: skill-creation
description: 'Create, improve, review, and evaluate Agent Skills with proper structure, progressive disclosure, trigger descriptions, evals, references, and bundled scripts. Use when the user asks about building, adding, improving, reviewing, or testing a skill; mentions "skill", "agent skill", or "SKILL.md"; or wants to teach the agent a repeatable workflow even without saying "skill".'
---

# Skill Creation

A skill is a folder with a `SKILL.md` file containing YAML frontmatter (`name`, `description`) and Markdown instructions. Skills give agents specialized knowledge and repeatable workflows through **progressive disclosure**: only descriptions load at startup; full instructions load on demand.

## Gotchas

- When improving an existing skill, do **not** start from a blank template. Read the current `SKILL.md`, relevant `references/*.md`, existing `evals/*.json`, and provenance files (`GENERATION.md` or `SYNC.md`) before editing.
- Evidence-first does not mean "block forever." If no traces or source artifacts exist, make a conservative hygiene pass, state the assumption, and add evals that will collect evidence on the next iteration.
- `scripts/test-skill.py --create-evals` creates scaffolding only. Replace placeholder prompts/assertions with realistic should-trigger, near-miss, and output-quality evals before treating evaluation as complete.
- Keep core behavior in `SKILL.md`. References are for depth; if the agent must read a reference to perform the basic workflow, promote that content into `SKILL.md`.
- Clean generated artifacts (`__pycache__/`, `*.pyc`, `evals/runs/`, temp run outputs) before sharing or packaging a skill.
- When behavior evals still require human judgment, do not just say "review manually"; point to `review.md` and name the exact stdout/session/workspace/assertion evidence to inspect.
- When editing a skill description or activation boundary, update or create `evals/trigger-queries.json` in the same pass with realistic should-trigger and near-miss prompts. Do not stop after changing only the description.
- Do not place fixture skills with real `SKILL.md` files under a discoverable skill tree; pi may load them as real skills. Store them as `SKILL.fixture.md` and use an output eval `files` mapping with `source` and `target` to copy them as `SKILL.md` inside the isolated workspace.
- For generated or synced skills, check provenance first and update `GENERATION.md`/`SYNC.md`; avoid local edits to synced skills when the fix belongs upstream.
- When applying the Existing Skill Improvement Workflow to the `skill-creation` skill itself, resolve `/path/to/skill-creation/` to the skill-creation skill's own directory so script paths work.
- YAML frontmatter is parsed before a skill loads. Quote `description` and other scalar values when they contain `: `, `#`, leading `{`/`[`, or embedded quotes; default generated skills to `description: "..."`. Unquoted text like `description: Use when writing tests: browser mode` can break discovery with YAML nested-mapping errors.

## The Iterative Build Loop

This is the core methodology — its principles (ground in evidence, write minimally, test, capture gotchas, iterate) underpin all skill work. For **creating** a new skill, follow this loop directly. For **improving** an existing skill, apply these same principles through the gated **Existing Skill Improvement Workflow** below.

### 1. Ground in real expertise

Start from concrete material, not generic knowledge:

- A completed hands-on task where you steered the agent through corrections
- Existing project artifacts: runbooks, style guides, incident reports, API specs
- Known failure cases and their resolutions
- Code review patterns that keep recurring

**Anti-pattern:** Writing a skill from what you _think_ the agent needs, without evidence. Skills grounded in real corrections ("the agent did X, but should have done Y") are 10x more effective than skills written from imagination.

For source-driven generation, read [source-driven-generation](references/source-driven-generation.md). Focus on agent capabilities, practical usage patterns, code/command examples, edge cases, and validation steps. Skip user-facing introductions, marketing, basic install/get-started material, and generic concepts agents already know.

### 2. Write a minimal first draft

Write the smallest SKILL.md that would have prevented the mistakes you observed. Start with:

- **A Gotchas section** — concrete corrections for mistakes the agent will make. This is often the highest-value content. Example:

  ```markdown
  ## Gotchas

  - The `users` table uses soft deletes. Always include
    `WHERE deleted_at IS NULL` or results will include deactivated accounts.
  - The user ID is `user_id` in the database, `uid` in the auth service,
    and `accountId` in the billing API. All three refer to the same value.
  ```

- **A workflow section** — the sequence of steps. Use checklists for multi-step workflows so the agent can track progress:

  ```markdown
  ## Workflow

  Progress:

  - [ ] Step 1: Analyze the form (`scripts/analyze_form.py`)
  - [ ] Step 2: Create field mapping (edit `fields.json`)
  - [ ] Step 3: Validate mapping (`scripts/validate_fields.py`)
  - [ ] Step 4: Fill the form (`scripts/fill_form.py`)
  - [ ] Step 5: Verify output (`scripts/verify_output.py`)
  ```

- **A validation loop** if the task has verifiable correctness criteria:

  ```markdown
  1. Make your edits
  2. Run validation: `python scripts/validate.py output/`
  3. If validation fails: review the error, fix, re-validate
  4. Only proceed when validation passes
  ```

Keep the first draft under 100 lines. Don't try to cover everything — you'll discover what's missing during testing.

### 3. Test with real prompts

Run the skill against 3-5 real tasks it should handle. Watch the execution:

- **Where does the agent waste steps?** Add guidance to skip them.
- **Where does the agent miss instructions?** Make those instructions more prominent.
- **Where does the agent make wrong assumptions?** Add to Gotchas.
- **Does the skill activate when it should?** If not, the description needs work.
- **Does it activate when it shouldn't?** Narrow the description.

### 4. Capture corrections as gotchas

When you have to steer the agent during a test run, add that correction to the Gotchas section immediately. This is the most direct way to improve a skill. Every gotcha represents a real mistake that actually happened — not a hypothetical.

### 5. Iterate with an LLM

Feed the SKILL.md, execution traces, and your observations to an LLM:

```
Here is my current skill. Here are execution traces from 3 test runs.
Here are the problems I observed: [list]. Propose specific
improvements to the SKILL.md that would prevent these problems.
```

Apply changes, re-test, repeat. Stop when the skill consistently produces good results without needing manual corrections.

## New Skill Creation Workflow

Use this when the user wants a new skill or wants to teach the agent a repeatable workflow.

1. **Gather requirements before writing files.** Ask for the task/domain, 2-4 concrete use cases, near-misses that should not trigger, whether deterministic scripts are needed, and any source material (runbooks, prior corrections, docs, examples).
2. **Pick the target structure.** Default to:

   ```text
   skill-name/
   ├── SKILL.md
   ├── references/        # optional one-level deep docs
   ├── scripts/           # optional deterministic helpers
   └── evals/             # trigger/output evals and fixtures
   ```

3. **Draft the smallest useful `SKILL.md`.** Keep the first draft under ~100 lines. Use this skeleton:

   ```markdown
   ---
   name: skill-name
   description: "Capability in third person. Use when specific triggers, contexts, keywords, or file types apply."
   ---

   # Skill Name

   ## Gotchas
   - Concrete corrections from source evidence.

   ## Workflow
   1. Read/inspect the required inputs.
   2. Do the task using the default tool or procedure.
   3. Validate with a command, checklist, or rubric.

   ## References
   Read `references/details.md` only for rare edge cases.
   ```

4. **Add support files only when they change behavior.** Add scripts for deterministic validation/formatting/repeated operations with explicit errors and `--help`. Split to one-level `references/*.md` when `SKILL.md` exceeds ~100 lines, content is rarely needed, or a distinct deep topic would distract from the core workflow.
5. **Create initial evals.** Add realistic should-trigger, near-miss, and output-quality cases; never leave scaffold placeholders in `evals/*.json`.
6. **Run the static gate.** Use `python /path/to/skill-creation/scripts/test-skill.py /path/to/new-skill` and fix errors before presenting the draft.
7. **Review with the user before expensive evals.** Ask: “Does this cover your use cases? Anything missing or unclear? Should any section be more/less detailed?” Only run live evals after the user approves or asks for them.

Quick final checklist: frontmatter parses as valid YAML, description has “Use when…” and is quoted when punctuation-heavy, `SKILL.md` is concise and self-contained, references are one level deep, terminology is consistent, examples are concrete, scripts are justified, evals are realistic, and no time-sensitive claims or generated artifacts are accidentally included.

## Existing Skill Improvement Workflow

Use this when the user asks to improve or review a skill that already exists.

This is the Iterative Build Loop applied to an existing skill — each phase maps to a Build Loop step:

| Phase | Build Loop step | What changes |
|---|---|---|
| 1. Assess | Ground in real expertise | Source material is the existing SKILL.md, references, and evals — not raw runbooks |
| 2. Edit | Write a minimal draft | You're editing, not drafting from scratch — smallest evidence-driven change |
| 3. Evaluate | Test with real prompts | Formal eval runner instead of ad-hoc testing |
| 4. Hand off | Capture corrections + Iterate | Human review replaces LLM iteration; feedback becomes gotchas |

The workflow is **gated** — do not skip steps. Each gate must pass before proceeding.

### Phase 1: Assess

- [ ] Locate the skill root and inspect current worktree state so you do not overwrite unrelated user changes.
- [ ] Read `SKILL.md`, relevant one-level references, existing eval files, and `GENERATION.md`/`SYNC.md` if present.
- [ ] Run the static gate to capture the starting point:

  ```bash
  python /path/to/skill-creation/scripts/test-skill.py /path/to/target-skill
  ```

  **Gate:** If the static gate has errors, fix those first. Do not proceed with behavior changes until the gate is clean.

- [ ] If `evals/trigger-queries.json` or `evals/output-evals.json` are missing or have placeholders, scaffold them:

  ```bash
  python /path/to/skill-creation/scripts/test-skill.py /path/to/target-skill --create-evals
  ```

  **Gate:** Replace all placeholder text in eval files with realistic content before running evals. The test output will list any remaining placeholders.

### Phase 2: Edit

- [ ] Identify the evidence for each change: static finding, user correction, execution trace, eval failure, or source artifact. If evidence is thin, keep the edit small and add eval coverage rather than inventing domain rules.
- [ ] Make the smallest behavior-changing edit: add observed corrections to `## Gotchas`, clarify skipped workflow steps, adjust the description boundary, fill eval placeholders, or move deep detail into a one-level reference.
- [ ] If you changed the skill description or activation boundary, update `evals/trigger-queries.json` in the same pass with realistic should-trigger and near-miss prompts. **Gate:** Do not proceed past Phase 2 without this — the eval runner will flag missing trigger queries as FAIL.
- [ ] Run the static gate again after editing:

  ```bash
  python /path/to/skill-creation/scripts/test-skill.py /path/to/target-skill
  ```

  **Gate:** Static gate must pass. Fix any new warnings before proceeding.

### Phase 3: Evaluate

- [ ] Run the automated eval runner with LLM judge (single pass):

  ```bash
  python /path/to/skill-creation/scripts/run-skill-evals.py /path/to/target-skill --mode all --llm-judge
  ```

  This runs trigger evals, output evals, and LLM assertion grading in one pass, then writes `evals/runs/<timestamp>/review.md`.

  **Runtime:** Expect 15–30 minutes for `--trigger-runs 3` (default) or 5–10 minutes with `--trigger-runs 1`. For full-confidence trigger rates, run 3 runs; for fast iteration, use `--trigger-runs 1` first, then re-run with 3 before handing off. For large eval suites, use the parallel subagent approach described in [Evaluating Skills](references/evaluating-skills.md).

  If the run times out, resume it — completed runs are skipped and only missing ones execute:

  ```bash
  python /path/to/skill-creation/scripts/run-skill-evals.py /path/to/target-skill --mode all --llm-judge --resume /path/to/target-skill/evals/runs/<timestamp>
  ```

  **Gate:** Check the printed summary. If command failures or timeouts occurred, inspect the stderr and retry (or resume) before proceeding.

- [ ] **Consolidate the results into one scannable file** for human review:

  ```bash
  python /path/to/skill-creation/scripts/consolidate-review.py /path/to/target-skill/evals/runs/<timestamp> --link-to /path/to/target-skill/LAST_REVIEW.md
  ```

  This produces a single `consolidated-review.md` with all outputs inlined — stdout, stderr, changed files, activation evidence, and an assertions checklist with LLM judge drafts. The `--link-to` flag creates a stable symlink at the skill root so the human can open `LAST_REVIEW.md` without navigating deep directories.

  **Gate:** The consolidation script must succeed. If it errors, fix the issue (usually a missing report.json) before proceeding.

### Phase 4: Hand off to human

The human does not re-read everything — the AI already ran all automated checks. The human answers specific questions about what the AI flagged as uncertain.

- [ ] **Present a summary with clear questions.** For each uncertain item, ask a concrete question the human can answer without opening files:
  - "The LLM judge marked assertion X as NEEDS_HUMAN_REVIEW because [reason]. Does the output satisfy this assertion?"
  - "Near-miss query Y falsely triggered. Should we narrow the description, or is this an acceptable edge case?"
  - "Manual review point Z: [question]. What do you see?"
- [ ] **Give the file path.** Tell the human the consolidated review is at `LAST_REVIEW.md` (at the skill root) — open it in any editor for full evidence if they want to drill deeper.
- [ ] **Use the interactive handoff when available.** If the `skill_review_human_handoff` tool exists, call it with the exact `skillDir` and eval `runDir`; it records human verdicts and links them from `LAST_REVIEW.md`.
- [ ] **Do not edit the skill further until the human responds or the handoff tool returns verdicts.** Treat returned FAIL/ISSUE verdicts as evidence for the next edit pass.
- [ ] **After human feedback, loop back to Phase 2.** Treat the human's answers as new evidence — edit the skill, rerun the static gate, then re-evaluate (Phase 3). Repeat until the human has no more corrections.
- [ ] **When the human is satisfied**, run the final cleanup check:

  ```bash
  find /path/to/target-skill -name '__pycache__' -type d -prune -exec rm -rf {} +
  ```

- [ ] Run these final hygiene checks:
  - Confirm `description` is specific, third-person, and under 1024 characters.
  - Verify `SKILL.md` is under 500 lines; move remaining detail to one-level reference files.
  - Add tables of contents to reference files over 100 lines.
  - Check terminology is consistent and time-sensitive claims are isolated in an "old patterns" section.
  - Test with the models/clients you expect to use — a skill clear enough for Opus may still be too terse for Haiku.
  - For source-derived skills, record source links and update `GENERATION.md` or `SYNC.md`.
- [ ] Summarize changed files, validation results, and any remaining manual evals.

## Core Principles

### Rewrite for agents, don't copy docs

Skills are executable guidance, not documentation mirrors. Synthesize source material into workflows, gotchas, defaults, and examples. If a paragraph doesn't change what the agent will do, cut it or move it to a reference file.

### Add what the agent lacks, omit what it knows

Challenge every sentence: "Would the agent get this wrong without this instruction?" If not, cut it. Don't explain what a PDF is or how HTTP works. Include project-specific conventions, domain procedures, non-obvious edge cases, and the particular tools or APIs to use.

### Design coherent units

A skill should encapsulate one coherent unit of work. Too narrow forces multiple skill loads; too broad makes precise activation hard. "Query a database and format the results" is one unit; adding "database administration" is probably too much.

See [When to Split vs. Grow](#when-to-split-vs-grow-a-skill) below for heuristics.

### Favor procedures over declarations

Teach the agent **how to approach** a class of problems, not what to produce for one specific instance. A reusable method (read schema → join by convention → apply filters → format) beats a specific query that only works for one table.

### Calibrate control to fragility

- **High freedom:** Multiple valid approaches, tolerant of variation. Explain _why_, not just _what_.
- **Low freedom:** Fragile operations, strict sequences, critical consistency. Give exact commands. Example: `python scripts/migrate.py --verify --backup` — do not modify.

Most skills mix both. Calibrate each part independently.

### Provide defaults, not menus

Pick a default tool/approach and mention alternatives briefly rather than presenting them as equal options. "Use pdfplumber. For scanned PDFs, fall back to pdf2image with pytesseract" beats listing all four PDF libraries.

### Keep SKILL.md self-contained enough to act on

The agent should be able to do useful work after reading only SKILL.md. Reference files are for edge cases and deep detail — not for core instructions. If the agent must read a reference to follow the basic workflow, the reference content belongs in SKILL.md.

## Common Anti-Patterns

These are the most frequent mistakes when writing skills. Check your skill against this list before testing.

| Anti-Pattern                         | Problem                                                                   | Fix                                                                                      |
| ------------------------------------ | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| SKILL.md is only a table of contents | Agent loads the skill but gets nothing actionable; must read 4 more files | Put core workflows, gotchas, and key instructions in SKILL.md. References for depth only |
| Too many options presented equally   | Agent wastes turns trying each                                            | Pick a default, mention alternatives briefly                                             |
| Explaining basics                    | Wastes tokens on what the agent already knows                             | Assume the agent knows what a PDF, HTTP, or database migration is                        |
| Deeply nested references             | Agent previews with `head -100`, misses content                           | All references one level deep from SKILL.md. No chains                                   |
| Exhaustive documentation             | Agent struggles to extract what's relevant                                | Concise, stepwise guidance with a working example                                        |
| No gotchas section                   | Agent repeats known mistakes that could have been prevented               | Add a Gotchas section with concrete corrections for environment-specific surprises       |
| Description too vague                | Skill never activates because the agent doesn't recognize when to use it  | Include key terms, user intents, and explicit contexts. Be pushy                         |
| No validation loop                   | Agent produces output but can't tell if it's correct                      | Add a validation step: run a script, check against a reference, or verify constraints    |
| Skill written from imagination       | Instructions address hypothetical problems, not real ones                 | Ground every instruction in a real mistake, real correction, or real project artifact    |

## When to Split vs. Grow a Skill

**Grow the skill** when the new capability:

- Shares the same trigger context (same description would activate for both)
- Uses the same tools, scripts, or domain knowledge
- Would feel natural as a subsection of the existing skill

**Split into a new skill** when:

- The description would need to cover two distinct user intents (e.g., "analyze data" vs. "manage database schema")
- SKILL.md approaches 500 lines and the new content is a coherent unit on its own
- The two capabilities use different tools or domain knowledge
- One capability could be useful independently (without loading the other)

**Merge two skills** when:

- They always activate together (the agent loads both for every task)
- Their descriptions overlap heavily, causing false activations
- One skill's workflow is a prerequisite for the other

## Writing Descriptions That Trigger

The description is the **sole mechanism** for skill discovery. If it doesn't convey when the skill is useful, the agent won't reach for it.

- **Use imperative phrasing.** "Use when..." rather than "This skill does..."
- **Focus on user intent, not implementation.** Describe what the user is trying to achieve.
- **Be pushy.** Explicitly list contexts: "Use when the user mentions 'skill', 'agent skill', 'SKILL.md', or wants to teach the agent a repeatable workflow — even if they don't use the word 'skill'."
- **Keep under 1024 characters.** Descriptions tend to grow during optimization — check the limit.
- **Write in third person.** Not "I can help" or "you can use this".

For systematic description optimization (trigger eval queries, train/validation splits, iteration loops), read [evaluating-skills](references/evaluating-skills.md).

## Structuring Reference Files

| Topic                                                                                                 | Reference                                                          |
| ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Frontmatter fields, naming rules, directory structure, progressive disclosure, validation             | [skill-structure](references/skill-structure.md)                   |
| Generating or updating skills from repositories, docs, upstream skills, and versioned source material | [source-driven-generation](references/source-driven-generation.md) |

Reference files should be **one level deep** from SKILL.md. Tell the agent _when_ to load each file: "Read `references/api-errors.md` if the API returns a non-200 status code" beats "see references/ for details."

For files longer than 100 lines, include a table of contents at the top so the agent can see the full scope even when previewing with partial reads.

## Writing Instructions

| Topic                                                                                                                           | Reference                                                  |
| ------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Checklists, validation loops, plan-validate-execute, templates, gotchas, calibrating specificity, progressive disclosure design | [writing-instructions](references/writing-instructions.md) |

Key patterns to use in SKILL.md:

- **Gotchas:** Environment-specific facts that defy reasonable assumptions. Add a correction every time the agent makes a mistake you have to steer.
- **Checklists:** For multi-step workflows with clear progress tracking.
- **Validation loops:** "Make edits → run validation → fix errors → repeat until pass."
- **Plan-Validate-Execute:** For batch or destructive operations. Create a plan, validate it against a source of truth, then execute.
- **Templates:** When output must follow a specific format, provide a concrete template. Agents pattern-match well against structures.

## Evaluation & Iteration

| Topic                                                                                                                 | Reference                                            |
| --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Trigger eval queries, optimizing descriptions, output quality evals, blind comparison, the eval-driven iteration loop | [evaluating-skills](references/evaluating-skills.md) |
| Universal automated + manual workflow for testing any skill                                                           | [testing-any-skill](references/testing-any-skill.md) |

For quick feedback without formal eval infrastructure:

1. Run the same prompt with and without the skill (baseline comparison).
2. Check: Did the skill activate? Did the output improve? Did it cost significantly more tokens?
3. If the skill didn't activate on a should-trigger prompt, the description is too narrow.
4. If it activated on a shouldn't-trigger prompt, the description is too broad.

### Automated eval runner

An **eval** is a test for whether a skill activates correctly and improves behavior. Use `scripts/run-skill-evals.py` to automate as much as pi allows:

```bash
python /path/to/skill-creation/scripts/run-skill-evals.py /path/to/skill --mode all
```

Eval types:

- **Trigger evals** test discovery: should the agent load this skill for this prompt? The runner starts fresh pi sessions with only the target skill available, detects whether the target `SKILL.md` was read, computes trigger rates, and flags false positives/negatives.
- **Output evals** test usefulness: does the skill improve task results? The runner copies listed fixture files into isolated workspaces, runs each prompt with the skill and a no-skill baseline, captures stdout/stderr/session logs, records changed files, and can draft assertion grading with `--llm-judge`.

Run modes:

- **Dry run** (`--dry-run`) does not call the model. It only writes the commands, checks fixture copying/path setup, and creates `report.json`/`review.md`. Use it to test the eval machinery.
- **Live model eval** omits `--dry-run`. It launches pi/model runs and actually tests skill activation and output quality.

Human review handoff: the runner writes `evals/runs/<timestamp>/review.md` with exact paths to outputs, sessions, workspaces, changed-file summaries, and assertion/manual-review items that still need judgment.

Keep eval fixtures under `evals/fixtures/` when possible so output evals are reproducible. Use `--run-dir /tmp/<name>` if you do not want eval artifacts under the skill directory.

### Parallel evaluation with subagents

Use the `pi-subagents` skill to run multiple test prompts concurrently:

```
Run these 5 test prompts with the skill active, each in a fresh context.
Collect execution traces and compare.
```

This dramatically speeds up the test → observe → improve loop.

## Scripts & Tools

| Topic                                                                                                             | Reference                                            |
| ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| One-off commands (uvx, npx, deno), self-contained scripts (PEP 723, Deno, Bun), designing scripts for agentic use | [scripts-and-tools](references/scripts-and-tools.md) |

Available scripts:

- **`scripts/test-skill.py`** — Runs universal static checks for any skill and prints the remaining manual/semi-automated eval workflow. Use `--create-evals` to scaffold `evals/trigger-queries.json` and `evals/output-evals.json`, then replace placeholders with realistic evals.

  ```bash
  # From the skill-creation skill directory:
  python scripts/test-skill.py /path/to/target-skill --create-evals

  # From anywhere else, resolve the script path first:
  python /path/to/skill-creation/scripts/test-skill.py /path/to/target-skill
  ```

- **`scripts/run-skill-evals.py`** — Runs trigger and output evals through pi, saves artifacts under `evals/runs/<timestamp>/`, and writes `review.md` telling the user exactly what still needs human judgment.

  ```bash
  python /path/to/skill-creation/scripts/run-skill-evals.py /path/to/target-skill --mode all
  python /path/to/skill-creation/scripts/run-skill-evals.py /path/to/target-skill --mode output --llm-judge
  ```

- **`scripts/consolidate-review.py`** — Inlines scattered eval artifacts into one scannable review file and optionally updates `LAST_REVIEW.md`.

  ```bash
  python /path/to/skill-creation/scripts/consolidate-review.py /path/to/target-skill/evals/runs/<timestamp> --link-to /path/to/target-skill/LAST_REVIEW.md
  ```

For script design rules (--help, error messages, structured output, idempotency, dry-run support), read [scripts-and-tools](references/scripts-and-tools.md).

## Compact Example

Weak skill: `description: "CSV helper."` plus “use pandas and handle errors.” It will not trigger reliably and gives no executable guidance.

Improved pattern:

```markdown
---
name: processing-csvs
description: "Clean, transform, analyze, and export CSV or spreadsheet-like text files. Use when the user mentions CSV, spreadsheets, delimited files, tabular text data, row cleanup, joins, filters, or CSV export."
---

# Processing CSVs

## Gotchas
- Our CSVs use semicolons (`;`), dates are `DD/MM/YYYY`, and blanks are `\N`.

## Workflow
1. Inspect schema: `scripts/load_csv.py <file> --delimiter ";"`
2. Transform using the requested filter/aggregate/join/reshape.
3. Validate: `scripts/validate_csv.py <output.csv>`; fix and re-run until it passes.
```

This works because the description has concrete triggers, the workflow names defaults, gotchas prevent observed mistakes, and validation closes the loop.

<!--
Source references:
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- https://github.com/antfu/skills/blob/main/AGENTS.md
- https://github.com/agentskills/agentskills (docs/skill-creation/, docs/specification.mdx)
-->
