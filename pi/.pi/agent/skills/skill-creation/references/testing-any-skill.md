---
name: testing-any-skill
description: Universal workflow for testing any Agent Skill with automated checks and manual/semi-automated eval steps.
---

# Testing Any Skill

Use this workflow to test a skill regardless of domain. The goal is to automate objective checks and produce clear manual instructions for anything that requires agent execution traces or human judgment.

## Contents

- [Workflow](#workflow)
- [Eval file schema](#eval-file-schema)
- [Trigger evals](#trigger-evals)
- [Output evals](#output-evals)
- [Trace review](#trace-review)
- [Decision rules](#decision-rules)

## Workflow

1. **Run the static gate** from the `skill-creation` skill directory, or use an absolute path to its bundled script:
   ```bash
   python scripts/test-skill.py /path/to/skill --create-evals
   python /path/to/skill-creation/scripts/test-skill.py /path/to/skill --create-evals
   ```
   This validates frontmatter, markdown links, line-count guidance, reference TOCs, common anti-patterns, eval file presence, and common generated artifacts.

2. **Fill generated eval templates**. `--create-evals` only scaffolds placeholders; it does not create meaningful tests.
   - `evals/trigger-queries.json` — should-trigger and near-miss prompts.
   - `evals/output-evals.json` — realistic tasks, expected outputs, assertions, and manual review points.

3. **Run trigger and output evals with the automated runner** when pi/model access is available:
   ```bash
   python scripts/run-skill-evals.py /path/to/skill --mode all
   ```
   This runs trigger prompts in fresh sessions, detects target `SKILL.md` reads, runs output prompts with-skill and baseline in isolated workspaces, records changed files, and writes `evals/runs/<timestamp>/review.md`.

4. **Read the generated review guide**. It tells the user where to look for each remaining human-only check: stdout/stderr, `sessions/**/*.jsonl`, workspaces, changed-file summaries, assertion lists, and manual review points.

5. **Grade assertions** with PASS/FAIL and concrete evidence. Use `--llm-judge` to draft assertion grading, but verify any subjective or trace-based PASS manually.

6. **Inspect execution traces**, not only final outputs. Trace review reveals wasted steps, missed references, false activations, and instructions the agent ignored.

7. **Edit the skill from evidence**. Add observed corrections as gotchas, tighten workflows, remove unused references, and rerun the static gate + affected evals.

## Eval file schema

`evals/trigger-queries.json`:

```json
{
  "skill_name": "my-skill",
  "queries": [
    {
      "id": "should-trigger-1",
      "query": "Realistic user prompt that should use the skill.",
      "should_trigger": true,
      "rationale": "Why this skill should be used."
    },
    {
      "id": "near-miss-1",
      "query": "Adjacent prompt that should not use the skill.",
      "should_trigger": false,
      "rationale": "Why this is out of scope."
    }
  ]
}
```

`evals/output-evals.json`:

```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": "core-workflow-1",
      "prompt": "Realistic task the skill should handle.",
      "files": [
        "evals/fixtures/input.md",
        {
          "source": "evals/fixtures/example-skill/SKILL.fixture.md",
          "target": "evals/fixtures/example-skill/SKILL.md"
        }
      ],
      "expected_output": "Human-readable description of success.",
      "assertions": [
        "Observable, verifiable assertion about output.",
        "Another assertion with concrete evidence."
      ],
      "manual_review": [
        "Check whether the agent followed the intended workflow.",
        "Check whether the agent loaded only relevant references."
      ]
    }
  ]
}
```

## Trigger evals

Build about 20 prompts:

- 8–10 should-trigger prompts covering explicit mentions, indirect descriptions, terse prompts, detailed prompts, typos, and larger tasks where the skill-relevant part is embedded.
- 8–10 should-not-trigger prompts focused on **near misses**. Avoid obvious negatives that prove nothing.

Pass criteria:

- `should_trigger: true` passes when trigger rate is above 0.5.
- `should_trigger: false` passes when trigger rate is below 0.5.

Automated runner:

```bash
python scripts/run-skill-evals.py /path/to/skill --mode trigger --trigger-runs 3
```

The runner uses pi session logs as evidence. It marks a query as triggered when a tool call reads the target skill's `SKILL.md`. If automation cannot run or the result looks wrong:

1. Open the query's run directory from `evals/runs/<timestamp>/review.md`.
2. Read `stdout.txt` and `stderr.txt` for obvious pi/model errors.
3. Inspect `sessions/**/*.jsonl` for a `read` tool call targeting the skill's `SKILL.md`.
4. Record `{query_id, run_number, triggered, evidence}`.

## Output evals

Start with 2–3 evals and expand after the first run. Include:

- One happy path for the core workflow.
- One edge case or ambiguous request.
- One task likely to expose a known gotcha or failure mode.

For each eval, the automated runner saves outputs under:

```text
evals/runs/<timestamp>/output/<eval-id>/with_skill/run-1/
evals/runs/<timestamp>/output/<eval-id>/baseline/run-1/
```

Each run directory contains `stdout.txt`, `stderr.txt`, `command.json`, `result.json`, `changed-files.json`, `workspace/`, and `sessions/`. If fixture files are missing, the eval is skipped and `review.md` lists exactly which files to create or fix.

Use a plain string in `files` when the source and workspace path are the same. Use `{ "source": "...", "target": "..." }` when a fixture needs a different stored name. This is especially important for fixture skills: store `SKILL.fixture.md` in the real repository and map it to `SKILL.md` in the eval workspace so pi does not discover fixture skills as real skills.

Grade each assertion as:

```json
{
  "text": "The output includes a valid JSON file.",
  "passed": true,
  "evidence": "Found output.json and jq parsed it successfully."
}
```

Require concrete evidence for PASS. If evidence is vague, mark FAIL or rewrite the assertion.

## Trace review

For each run, inspect:

- Did the skill activate when expected?
- Did the agent load the right reference files?
- Did it ignore any instruction?
- Did it waste time on unproductive steps?
- Did it invent scripts or logic that should be bundled?
- Did it copy source docs verbatim instead of synthesizing?
- Did validation catch errors before final output?

Turn trace observations into skill edits:

- Repeated wrong assumption → add to `## Gotchas`.
- Repeated skipped step → make workflow/checklist more explicit.
- Repeated helper code → bundle a script.
- Repeated unnecessary read → move/cut/rename references or clarify when to read them.
- False trigger → narrow the description boundary.
- Missed trigger → broaden description with user intent language.

## Decision rules

A skill is ready enough to share when:

- Static gate has no errors.
- Trigger evals pass on the validation set or manual spot checks are consistently correct.
- Output evals improve over baseline enough to justify token/time cost.
- Human review feedback is empty or non-blocking.
- The same correction is not needed twice in trace review.

Stop iterating when pass rates plateau, feedback becomes minor, or new instructions add more complexity than benefit.

<!--
Source references:
- https://github.com/agentskills/agentskills/blob/main/docs/skill-creation/evaluating-skills.mdx
- https://github.com/agentskills/agentskills/blob/main/docs/skill-creation/optimizing-descriptions.mdx
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#evaluation-and-iteration
-->
