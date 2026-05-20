---
name: evaluating-skills
description: How to evaluate skill triggering accuracy and output quality, and iterate systematically.
---

# Evaluating Skills

## Contents

- [Overview](#overview)
- [Optimizing Descriptions (Triggering)](#optimizing-descriptions-triggering)
- [Evaluating Output Quality](#evaluating-output-quality)
- [The Iteration Loop](#the-iteration-loop)
- [Blind comparison](#blind-comparison)

## Overview

Skills need evaluation on two axes:

1. **Triggering accuracy** — does the skill activate on the right prompts and not on the wrong ones?
2. **Output quality** — when activated, does the skill produce correct, complete, well-structured results?

## Optimizing Descriptions (Triggering)

The `description` field is the sole mechanism for skill discovery. If it doesn't convey when the skill is useful, the agent won't reach for it.

### Writing effective descriptions

- **Use imperative phrasing.** "Use this skill when..." rather than "This skill does..." The agent is deciding whether to act — tell it when.
- **Focus on user intent, not implementation.** Describe what the user is trying to achieve, not the skill's internal mechanics.
- **Err toward being pushy.** Explicitly list contexts: "even if they don't explicitly mention 'CSV' or 'analysis.'"
- **Keep under 1024 characters.** Descriptions tend to grow during optimization — check the limit after each revision.

### Creating trigger eval queries

Build a set of ~20 realistic user prompts labeled `should_trigger: true/false`:

```json
[
  { "query": "I've got a spreadsheet in ~/data/q4_results.xlsx with revenue in col C — can you add a profit margin column?", "should_trigger": true },
  { "query": "whats the quickest way to convert this json file to yaml", "should_trigger": false }
]
```

**Should-trigger queries:** Vary phrasing (formal/casual/typos), explicitness (names domain directly vs. describes need), detail (terse to context-heavy), and complexity (single-step to multi-step).

**Should-not-trigger queries:** Focus on **near-misses** — queries that share keywords but need something different. For a CSV analysis skill, "I need to update formulas in my Excel budget spreadsheet" is a strong negative; "Write a fibonacci function" tests nothing.

**Realism matters:** Include file paths, personal context ("my manager asked me to..."), specific details (column names, company names), and casual language with occasional typos.

### Testing trigger rates

Run each query through the agent with the skill installed. Run each query 3+ times (model behavior is nondeterministic). Compute a **trigger rate**: fraction of runs where the skill was invoked.

A query passes if:
- `should_trigger: true` and trigger rate > 0.5
- `should_trigger: false` and trigger rate < 0.5

### Avoiding overfitting

Split queries into **train set** (~60%) and **validation set** (~40%). Use train failures to guide description changes; use validation set to check if improvements generalize. Keep the split fixed across iterations.

### The optimization loop

1. **Evaluate** current description on train + validation sets
2. **Identify failures** in train set (use only train failures for guidance)
3. **Revise** the description:
   - Failing should-trigger → description too narrow, broaden scope
   - False-triggering → description too broad, add specificity about boundaries
   - Avoid adding specific keywords from failed queries (overfitting)
   - If stuck, try a structurally different approach rather than incremental tweaks
4. **Repeat** until train passes or improvement plateaus
5. **Select best iteration** by validation pass rate (may not be the last one)

Five iterations is usually enough. If performance isn't improving, the queries may be the issue (too easy, too hard, or poorly labeled).

## Evaluating Output Quality

### Designing test cases

A test case has: a realistic prompt, an expected output description, and optional input files:

```json
{
  "id": 1,
  "prompt": "I have a CSV of monthly sales in data/sales.csv. Find top 3 months by revenue and make a bar chart.",
  "expected_output": "A bar chart image showing the top 3 months by revenue, with labeled axes.",
  "files": ["evals/files/sales.csv"]
}
```

- Start with 2-3 test cases. Expand after the first round of results.
- Vary phrasing, detail level, and formality.
- Include at least one edge case (malformed input, ambiguous instructions, boundary condition).
- Use realistic context: file paths, column names, personal details.

### Running evals

**Automated pi runner:** Prefer the bundled runner when evaluating skills in pi:

```bash
python scripts/run-skill-evals.py /path/to/skill --mode all
```

It runs trigger queries in fresh sessions, detects whether the target `SKILL.md` was read, runs output evals with the skill and a no-skill baseline in isolated workspaces, captures session logs and changed files, and writes `review.md` with exact human-review instructions. Add `--llm-judge` to draft assertion grading, then verify subjective PASS grades manually.

**Parallel execution:** Use a subagent system (such as `pi-subagents`) to run multiple test cases concurrently, each in a fresh context. This dramatically speeds up the test → observe → improve loop compared to sequential execution:

```
Run these 5 test prompts with the skill active, each in a separate
subagent with fresh context. Collect all execution traces and
compare the outputs.
```

**Per test case:** Run each test case **with the skill** and **without it** (baseline). This gives you a delta: what does the skill actually improve? When improving an existing skill, snapshot the previous version and compare `new_skill` against `old_skill` instead of `without_skill`.

Test with every model/client you expect to support. If the skill works on a stronger model but fails on a cheaper/faster one, add only the minimum guidance needed to close that gap.

For each run, capture:
- Output files produced
- Token count and duration (`timing.json`)
- Fresh context per run — no leftover state from previous runs

### Writing assertions

Assertions are verifiable statements about output. Add them **after** seeing the first round of results — you often don't know what "good" looks like until the skill has run.

**Good:** "The bar chart has labeled axes" (specific, observable), "The output file is valid JSON" (programmatically verifiable), "The report includes at least 3 recommendations" (countable).

**Weak:** "The output is good" (too vague), "The output uses exactly the phrase 'Total Revenue: $X'" (too brittle).

Not everything needs an assertion. Qualities like writing style or visual design are better caught by human review.

### Grading

For each assertion, record **PASS** or **FAIL** with concrete evidence:

```json
{
  "text": "The chart shows exactly 3 months",
  "passed": true,
  "evidence": "Chart displays bars for March, July, and November"
}
```

- **Require concrete evidence for PASS.** Don't give the benefit of the doubt.
- **Review the assertions themselves.** Fix assertions that always pass (too easy), always fail (too hard), or are unverifiable.

For mechanical checks (valid JSON, row counts), use verification scripts — more reliable than LLM judgment.

### Aggregating results

```json
{
  "run_summary": {
    "with_skill": { "pass_rate": { "mean": 0.83 } },
    "without_skill": { "pass_rate": { "mean": 0.33 } },
    "delta": { "pass_rate": 0.50 }
  }
}
```

The delta tells you what the skill costs (more tokens, more time) and what it buys (higher pass rate).

### Pattern analysis

- Remove assertions that always pass in both configurations (don't discriminate)
- Investigate assertions that always fail in both (broken assertions or overly hard test cases)
- Study assertions that pass with skill but fail without (this is where the skill adds value)
- Check for inconsistency across runs (high variance → ambiguous instructions → add examples)

## The Iteration Loop

1. **Collect signals:** failed assertions, human reviewer feedback, execution transcripts
2. **Give all three + current SKILL.md to an LLM** and ask it to propose improvements
3. **Apply changes** with these principles:
   - Generalize from feedback — fixes should address underlying issues, not specific examples
   - Keep the skill lean — fewer, better instructions often outperform exhaustive rules
   - Explain the why — reasoning-based instructions beat rigid directives
   - Bundle repeated work — if every run writes the same helper script, bundle it in `scripts/`
4. **Rerun all test cases** in a new iteration
5. **Grade, aggregate, review.** Repeat until satisfied or no meaningful improvement

Stop when feedback is consistently empty, pass rates plateau, or you're satisfied with the delta between with-skill and without-skill performance.

### Blind comparison

For comparing two skill versions, present both outputs to an LLM judge without revealing which came from which. The judge scores holistic qualities (organization, formatting, usability, polish) free from bias about which version "should" be better. Two outputs might both pass all assertions but differ significantly in overall quality.

<!--
Source references:
- https://github.com/agentskills/agentskills/blob/main/docs/skill-creation/evaluating-skills.mdx
- https://github.com/agentskills/agentskills/blob/main/docs/skill-creation/optimizing-descriptions.mdx
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#evaluation-and-iteration
-->
