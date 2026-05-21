import { existsSync } from "node:fs";
import { join, basename } from "node:path";
import { listDirFiles, scriptPath } from "./paths";

/** Build the agent prompt that drives the full improvement workflow. */
export function buildImprovementMessage(
  skillDir: string,
  methodologySkillDir: string,
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
    "",
    "---",
    "",
    "## Files to read before editing",
    "",
    `- **\`${skillDir}/SKILL.md\`** — current skill body`,
  ];

  for (const provenanceFile of provenanceFiles) {
    parts.push(
      `- **\`${join(skillDir, provenanceFile)}\`** — provenance`,
    );
  }

  if (referenceFiles.length > 0) {
    parts.push(
      `- **Reference files** (${referenceFiles.length}): ${referenceFiles.map((file) => `\`${join(skillDir, "references", file)}\``).join(", ")}`,
    );
  }

  if (hasTriggerQueries) {
    parts.push(`- **\`${skillDir}/evals/trigger-queries.json\`**`);
  }

  if (hasOutputEvals) {
    parts.push(`- **\`${skillDir}/evals/output-evals.json\`**`);
  }

  parts.push(
    "",
    "---",
    "",
    "## Workflow",
    "",
    "Follow the **Existing Skill Improvement Workflow** from the skill-creation methodology. If you need the full methodology, read:",
    `\`${join(methodologySkillDir, "SKILL.md")}\``,
    "",
    "Go through all four phases (Assess, Edit, Evaluate, Hand off) on the target skill.",
    "",
    "### Phase 1: Assess",
    "",
    "Read all relevant files. Run the static gate:",
    "```bash",
    `python3 ${scriptPath("test-skill.py")} ${skillDir}`,
    "```",
    "If the static gate has errors, fix them before proceeding. If evals are missing or have placeholders, scaffold them with:",
    "```bash",
    `python3 ${scriptPath("test-skill.py")} ${skillDir} --create-evals`,
    "```",
    "Then replace all placeholder text before running evals.",
    "",
    "### Phase 2: Edit",
    "",
    "Make evidence-driven changes to SKILL.md. Add observed corrections to Gotchas, fix the description boundary, adjust references. Run the static gate again after editing.",
    "",
    "### Phase 3: Evaluate",
    "",
    "Run evals and LLM judge in a single command:",
    "```bash",
    `python3 ${scriptPath("run-skill-evals.py")} ${skillDir} --mode all --llm-judge`,
    "```",
    "This produces a run directory under `evals/runs/<timestamp>/`. Note the exact timestamp.",
    "Then consolidate results with that timestamp:",
    "```bash",
    `python3 ${scriptPath("consolidate-review.py")} ${skillDir}/evals/runs/<timestamp> --link-to ${skillDir}/LAST_REVIEW.md`,
    "```",
    "",
    "### Phase 4: Hand off to human",
    "",
    "When evaluation and consolidation are done, call `skill_review_human_handoff` with both the skill path AND the exact run directory path. Do NOT edit the skill further after calling this tool — wait for human feedback.",
    "",
    `Call: \`skill_review_human_handoff\` with \`skillDir: "${skillDir}"\` and \`runDir: "${skillDir}/evals/runs/<timestamp>"\``,
  );

  return parts.join("\n");
}
