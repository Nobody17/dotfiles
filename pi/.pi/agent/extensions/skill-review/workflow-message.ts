import { existsSync } from "node:fs";
import { join, basename } from "node:path";
import { listDirFiles, scriptPath } from "./paths";
import type { SkillCreateCommandOptions, SkillReviewCommandOptions } from "./args";

function formatCommand(commandParts: string[]): string {
  return commandParts
    .map((part) => (part.includes(" ") ? JSON.stringify(part) : part))
    .join(" ");
}

function evalCommandParts(skillDir: string, options: SkillReviewCommandOptions): string[] {
  const commandParts = [
    "python3",
    scriptPath("run-skill-evals.py"),
    skillDir,
    "--mode",
    options.mode,
  ];

  if (options.triggerRuns !== undefined) {
    commandParts.push("--trigger-runs", String(options.triggerRuns));
  }
  if (options.dryRun) commandParts.push("--dry-run");
  if (!options.noLlmJudge && !options.dryRun) commandParts.push("--llm-judge");
  if (options.resumeRunDir) commandParts.push("--resume", options.resumeRunDir);

  return commandParts;
}

function optionSummary(options: SkillReviewCommandOptions): string[] {
  const lines: string[] = [];
  if (options.quick) lines.push("- Speed profile: quick (`--trigger-runs 1`).");
  if (options.full) lines.push("- Speed profile: full confidence trigger runs.");
  if (options.dryRun) lines.push("- Dry-run eval machinery only; do not call live models from eval scripts.");
  if (options.noEvals) lines.push("- No eval run requested; stop after edits and static validation unless the user asks to continue.");
  if (options.noLlmJudge) lines.push("- Skip LLM assertion judge drafts.");
  if (options.triggerRuns !== undefined) lines.push(`- Trigger runs per query: ${options.triggerRuns}.`);
  if (options.mode !== "all") lines.push(`- Eval mode: ${options.mode}.`);
  if (options.resumeRunDir) lines.push(`- Resume eval run: \`${options.resumeRunDir}\`.`);
  return lines;
}

/** Build the agent prompt that drives the full improvement workflow. */
export function buildImprovementMessage(
  skillDir: string,
  methodologySkillDir: string,
  options: SkillReviewCommandOptions,
): string {
  const skillName = basename(skillDir);

  const referenceFiles = listDirFiles(join(skillDir, "references"), ".md");
  const evalDir = join(skillDir, "evals");
  const hasTriggerQueries = existsSync(join(evalDir, "trigger-queries.json"));
  const hasOutputEvals = existsSync(join(evalDir, "output-evals.json"));
  const provenanceFiles = ["GENERATION.md", "SYNC.md"].filter((file) =>
    existsSync(join(skillDir, file)),
  );

  const parts: string[] = [
    `Improve the **${skillName}** skill. Read files on demand — paths are listed below.`,
    "",
    `**Path:** \`${skillDir}\``,
  ];

  const optionLines = optionSummary(options);
  if (optionLines.length > 0) {
    parts.push("", "**Requested run options:**", ...optionLines);
  }

  parts.push(
    "",
    "---",
    "",
    "## Files to read before editing",
    "",
    `- **\`${skillDir}/SKILL.md\`** — current skill body`,
  );

  for (const provenanceFile of provenanceFiles) {
    parts.push(`- **\`${join(skillDir, provenanceFile)}\`** — provenance`);
  }

  if (referenceFiles.length > 0) {
    parts.push(
      `- **Reference files** (${referenceFiles.length}): ${referenceFiles
        .map((file) => `\`${join(skillDir, "references", file)}\``)
        .join(", ")}`,
    );
  }

  if (hasTriggerQueries) parts.push(`- **\`${skillDir}/evals/trigger-queries.json\`**`);
  if (hasOutputEvals) parts.push(`- **\`${skillDir}/evals/output-evals.json\`**`);

  parts.push(
    "",
    "---",
    "",
    "## Workflow",
    "",
    "Follow the **Existing Skill Improvement Workflow** from the skill-creation methodology. If you need the full methodology, read:",
    `\`${join(methodologySkillDir, "SKILL.md")}\``,
    "",
    "Go through Assess → Edit → Evaluate → Hand off. Keep edits evidence-driven and minimal.",
    "",
    "### Phase 1: Assess",
    "",
    "Read all relevant files. Run the static gate:",
    "```bash",
    formatCommand(["python3", scriptPath("test-skill.py"), skillDir]),
    "```",
    "If the static gate has errors, fix them before proceeding. If evals are missing or have placeholders, scaffold them with:",
    "```bash",
    formatCommand(["python3", scriptPath("test-skill.py"), skillDir, "--create-evals"]),
    "```",
    "Then replace all placeholder text before running evals.",
    "",
    "### Phase 2: Edit",
    "",
    "Make evidence-driven changes to SKILL.md, references, scripts, or evals. If you change the description boundary, update trigger evals in the same pass. Run the static gate again after editing.",
  );

  if (options.noEvals) {
    parts.push(
      "",
      "### Phase 3: Evaluate",
      "",
      "The user requested `--no-evals`. Do not run live evals in this pass. Summarize the static validation results and the exact eval command to run later.",
    );
  } else {
    const evalCommand = formatCommand(evalCommandParts(skillDir, options));
    parts.push(
      "",
      "### Phase 3: Evaluate",
      "",
      "Run evals with the requested options:",
      "```bash",
      evalCommand,
      "```",
      "This produces a run directory under `evals/runs/<timestamp>/`. Note the exact timestamp.",
      "Then consolidate results with that timestamp:",
      "```bash",
      formatCommand([
        "python3",
        scriptPath("consolidate-review.py"),
        join(skillDir, "evals", "runs", "<timestamp>"),
        "--link-to",
        join(skillDir, "LAST_REVIEW.md"),
      ]),
      "```",
      "",
      "### Phase 4: Hand off to human",
      "",
      "When evaluation and consolidation are done, call `skill_review_human_handoff` with both the skill path AND the exact run directory path. Do not make further edits until the human review verdicts are returned.",
      "",
      `Call: \`skill_review_human_handoff\` with \`skillDir: "${skillDir}"\` and \`runDir: "${skillDir}/evals/runs/<timestamp>"\``,
      "",
      "After the tool returns, use any FAIL/ISSUE verdicts as evidence and loop back to Phase 2.",
    );
  }

  return parts.join("\n");
}

function creationOptionSummary(options: SkillCreateCommandOptions): string[] {
  const lines: string[] = [];
  if (options.skillName) lines.push(`- Proposed skill name: ${options.skillName}`);
  if (options.targetDir) lines.push(`- Target directory: \`${options.targetDir}\``);
  if (options.scope) lines.push(`- Scope: ${options.scope}`);
  if (options.taskDomain) lines.push(`- Task/domain: ${options.taskDomain}`);
  if (options.useCases) lines.push(`- Use cases: ${options.useCases}`);
  if (options.needsScripts !== undefined) lines.push(`- Needs scripts: ${options.needsScripts ? "yes" : "no"}`);
  if (options.referenceMaterials) lines.push(`- Reference material: ${options.referenceMaterials}`);
  if (options.noEvals) lines.push("- Do not run live evals in the first pass.");
  if (options.dryRun) lines.push("- Dry-run any eval machinery only.");
  return lines;
}

export function buildCreationMessage(
  methodologySkillDir: string,
  options: SkillCreateCommandOptions,
): string {
  const parts: string[] = [
    "Create a new Agent Skill using the skill-creation methodology.",
    "",
    "If any requirement below is missing or ambiguous, ask concise clarifying questions before creating files.",
    "",
    "## Known requirements",
    "",
    ...creationOptionSummary(options),
    "",
    "## Methodology",
    "",
    `Read \`${join(methodologySkillDir, "SKILL.md")}\` and follow the **New Skill Creation Workflow**.`,
    "",
    "Required process:",
    "1. Gather requirements: task/domain, concrete use cases, scripts needed, and reference material.",
    "2. Draft a concise SKILL.md with actionable workflow, gotchas, validation, and a specific third-person description whose second sentence starts with `Use when...`.",
    "3. Add reference files only for depth; keep core behavior in SKILL.md. Add scripts only for deterministic repeatable operations.",
    "4. Create initial trigger and output evals unless the user explicitly requested no evals.",
    "5. Run the static gate with `test-skill.py`.",
    "6. Present the draft and ask the user whether it covers their use cases before expensive live evals.",
    "7. After user approval, run evals/consolidation/human handoff if requested.",
  ];

  return parts.join("\n");
}
