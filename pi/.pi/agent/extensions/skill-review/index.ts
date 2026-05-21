import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  realpathSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { join, basename } from "node:path";

// ── Path helpers ──────────────────────────────────────────────────

function piDir(): string {
  return process.env.PI_CODING_AGENT_DIR ?? join(homedir(), ".pi", "agent");
}

const SKILL_CREATION_DIR = join(piDir(), "skills", "skill-creation");

function scriptPath(name: string): string {
  return join(SKILL_CREATION_DIR, "scripts", name);
}

/** Recursively discover skills under a directory, returning absolute paths. */
function discoverSkillsUnder(dir: string): string[] {
  if (!existsSync(dir)) return [];
  const skills: string[] = [];
  const visitedDirs = new Set<string>();

  function directoryRealPath(path: string): string | null {
    try {
      const stat = statSync(path);
      if (!stat.isDirectory()) return null;
      return realpathSync(path);
    } catch {
      return null;
    }
  }

  try {
    const stack: string[] = [dir];
    while (stack.length > 0) {
      const current = stack.pop()!;
      const currentRealPath = directoryRealPath(current);
      if (!currentRealPath || visitedDirs.has(currentRealPath)) continue;
      visitedDirs.add(currentRealPath);

      if (existsSync(join(current, "SKILL.md"))) {
        skills.push(current);
      }

      for (const entry of readdirSync(current, { withFileTypes: true })) {
        const full = join(current, entry.name);
        if (entry.isDirectory() || entry.isSymbolicLink()) {
          stack.push(full);
        }
      }
    }
  } catch {
    // Permission errors, etc.
  }
  return skills;
}

function discoverSkills(cwd?: string): string[] {
  const agentDir = piDir();
  const dirs: string[] = [
    join(agentDir, "skills"),
    join(homedir(), ".agents", "skills"),
  ];
  const effectiveCwd = cwd ?? process.cwd();
  const projectSkills = join(effectiveCwd, ".pi", "skills");
  if (existsSync(projectSkills)) dirs.push(projectSkills);
  const agentsSkills = join(effectiveCwd, ".agents", "skills");
  if (existsSync(agentsSkills)) dirs.push(agentsSkills);

  const skills: string[] = [];
  for (const dir of dirs) {
    skills.push(...discoverSkillsUnder(dir));
  }
  return skills;
}

function findLatestRunDir(skillDir: string): string | null {
  const runsDir = join(skillDir, "evals", "runs");
  if (!existsSync(runsDir)) return null;
  const entries = readdirSync(runsDir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort()
    .reverse();
  return entries.length > 0 ? join(runsDir, entries[0]) : null;
}

function safeReadFile(filePath: string): string | null {
  if (!existsSync(filePath)) return null;
  try {
    return readFileSync(filePath, "utf-8");
  } catch {
    return null;
  }
}

function listDirFiles(dir: string, extension?: string): string[] {
  if (!existsSync(dir)) return [];
  try {
    return readdirSync(dir, { withFileTypes: true })
      .filter((e) => e.isFile() && (!extension || e.name.endsWith(extension)))
      .map((e) => e.name);
  } catch {
    return [];
  }
}

// ── Report parsing ────────────────────────────────────────────────

interface VariantResult {
  variant: string;
  run_number: number;
  command_result: {
    returncode: number | null;
    timed_out: boolean;
    stdout_path: string;
    stderr_path: string;
  } | null;
  activated_skill: boolean;
  changed_files: Record<string, string[]>;
  run_dir: string;
}

interface EvalReport {
  skill_dir: string;
  run_dir: string;
  created_at: string;
  trigger_summary: { total: number; passed: number; failed: number };
  output_summary: {
    total: number;
    completed: number;
    skipped: number;
    command_failures: number;
  };
  trigger_results: Array<{
    query_id: string;
    query: string;
    should_trigger: boolean;
    trigger_rate: number;
    passed: boolean;
    runs: Array<{
      run_number: number;
      triggered: boolean;
      activation_evidence: string[];
      run_dir: string;
    }>;
  }>;
  output_results: Array<{
    eval_id: string;
    prompt: string;
    expected_output: string | null;
    assertions: string[];
    manual_review: string[];
    judge_output_path: string | null;
    variants: VariantResult[];
  }>;
}

function loadReport(runDir: string): EvalReport | null {
  const reportPath = join(runDir, "report.json");
  if (!existsSync(reportPath)) return null;
  try {
    return JSON.parse(readFileSync(reportPath, "utf-8")) as EvalReport;
  } catch {
    return null;
  }
}

// ── Interactive human review ──────────────────────────────────────

interface Verdict {
  eval_id: string;
  assertions: { text: string; verdict: string }[];
  manual_review: { text: string; verdict: string }[];
  notes?: string;
}

function safeFileSegment(value: string): string {
  return value.replace(/[^a-zA-Z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "eval";
}

function fencedBlock(language: string, content: string): string {
  let longestRun = 0;
  let currentRun = 0;
  for (const character of content) {
    if (character === "`") {
      currentRun += 1;
      longestRun = Math.max(longestRun, currentRun);
    } else {
      currentRun = 0;
    }
  }
  const fence = "`".repeat(Math.max(3, longestRun + 1));
  return `${fence}${language}\n${content}\n${fence}`;
}

async function interactiveReview(
  ctx: ExtensionContext,
  report: EvalReport,
  skillDir: string,
  runDir: string,
) {
  if (!ctx.hasUI) return;

  const verdicts: Verdict[] = [];

  // Trigger evals — summary with command failure warning
  if (report.trigger_results.length > 0) {
    const passed = report.trigger_summary.passed;
    const total = report.trigger_summary.total;
    const commandFailures = report.output_summary.command_failures ?? 0;

    let warning = "";
    if (commandFailures > 0) {
      warning = `\n\n⚠️ ${commandFailures} command failure(s)/timeout(s). Some eval results may be incomplete.`;
    }

    const failList = report.trigger_results
      .filter((r) => !r.passed)
      .map((r) => `❌ ${r.query_id}: ${r.query}`)
      .join("\n");

    const proceed = await ctx.ui.confirm(
      "Trigger Evals",
      `${passed}/${total} trigger queries passed.${warning}\n\n${
        failList || "All passed!"
      }\n\nContinue to output evals?`,
    );
    if (!proceed) return;
  }

  // Output evals — interactive grading with evidence

  // Warn about command failures once before the output-eval grading loop
  if (report.output_summary.command_failures > 0) {
    const acknowledged = await ctx.ui.confirm(
      "⚠️ Command Failures",
      `${report.output_summary.command_failures} eval command(s) timed out or failed. Some output-eval results may be incomplete.`,
    );
    if (!acknowledged) return;
  }

  for (const evalResult of report.output_results) {
    if (!evalResult.assertions.length && !evalResult.manual_review.length)
      continue;

    const verdict: Verdict = {
      eval_id: evalResult.eval_id,
      assertions: [],
      manual_review: [],
    };

    // Build full evidence display. Keep this untruncated and write it to
    // disk before showing any dialogs; modal dialogs may clip long content,
    // but the evidence file and scrollable editor preserve the complete text.
    const evidenceLines: string[] = [
      `**Eval:** ${evalResult.eval_id}`,
      "",
      "**Prompt:**",
      evalResult.prompt,
    ];
    if (evalResult.expected_output) {
      evidenceLines.push(
        "",
        "**Expected:**",
        evalResult.expected_output,
      );
    }

    if (evalResult.assertions.length > 0 || evalResult.manual_review.length > 0) {
      evidenceLines.push("", "**Questions to answer:**");
    }

    if (evalResult.assertions.length > 0) {
      evidenceLines.push(
        "",
        "Assertions:",
        ...evalResult.assertions.map(
          (assertion) => `- Does the output satisfy this assertion? ${assertion}`,
        ),
      );
    }

    if (evalResult.manual_review.length > 0) {
      evidenceLines.push(
        "",
        "Manual review:",
        ...evalResult.manual_review.map(
          (item) => `- Does this manual review item look OK, or does it reveal an issue? ${item}`,
        ),
      );
    }

    // Per-variant outputs (stdout, stderr, changed files)
    if (evalResult.variants && evalResult.variants.length > 0) {
      for (const variant of evalResult.variants) {
        evidenceLines.push(
          "",
          `── ${variant.variant} (run ${variant.run_number}) ──`,
        );
        const cr = variant.command_result;
        if (cr) {
          evidenceLines.push(
            `Return code: ${cr.returncode ?? "?"} | Timed out: ${cr.timed_out} | ${variant.activated_skill ? "[SKILL RUN]" : "[BASELINE — no skill]"}`,
          );
          // Changed files summary
          if (variant.changed_files) {
            const entries = Object.entries(variant.changed_files).filter(
              ([, v]) => Array.isArray(v) && v.length > 0,
            );
            if (entries.length > 0) {
              evidenceLines.push(
                "Changed files:\n" +
                  entries.map(([k, v]) => `  ${k}: ${(v as string[]).join(", ")}`).join("\n"),
              );
            }
          }
          const stdout = safeReadFile(cr.stdout_path);
          if (stdout) {
            evidenceLines.push("stdout:", fencedBlock("text", stdout));
          }
          const stderr = safeReadFile(cr.stderr_path);
          if (stderr && stderr.trim()) {
            evidenceLines.push("stderr:", fencedBlock("text", stderr));
          }
        } else {
          evidenceLines.push("(no command result — may have been skipped)");
        }
      }
    }

    // LLM judge output
    if (evalResult.judge_output_path) {
      const judgeText = safeReadFile(evalResult.judge_output_path);
      if (judgeText) {
        evidenceLines.push(
          "",
          `**LLM Judge:**`,
          fencedBlock("markdown", judgeText),
        );
      }
    }

    const evidenceText = evidenceLines.join("\n") + "\n";
    const evidenceDir = join(runDir, "interactive-review-evidence");
    mkdirSync(evidenceDir, { recursive: true });
    const evidencePath = join(evidenceDir, `${safeFileSegment(evalResult.eval_id)}.md`);
    writeFileSync(evidencePath, evidenceText, "utf-8");

    ctx.ui.notify(
      `Full review evidence written for ${evalResult.eval_id}: ${evidencePath}`,
      "info",
    );

    // ctx.ui.select only accepts string[], so we use label strings and
    // map back to verdict codes after selection.
    const ASSERTION_LABELS = ["✅ PASS", "❌ FAIL", "⏭️ SKIP"];
    const ASSERTION_TO_VERDICT: Record<string, string> = {
      "✅ PASS": "PASS",
      "❌ FAIL": "FAIL",
      "⏭️ SKIP": "SKIP",
    };
    const REVIEW_LABELS = ["✅ OK", "❌ Issue found", "⏭️ SKIP"];
    const REVIEW_TO_VERDICT: Record<string, string> = {
      "✅ OK": "OK",
      "❌ Issue found": "ISSUE",
      "⏭️ SKIP": "SKIP",
    };

    // Grade assertions. Each item opens a scrollable question document first,
    // then asks for the verdict directly (PASS/FAIL/SKIP), avoiding yes/no-only review screens.
    for (const [index, assertion] of evalResult.assertions.entries()) {
      const question = [
        `# Assertion ${index + 1}/${evalResult.assertions.length}: ${evalResult.eval_id}`,
        "",
        "## Question",
        "Does the output satisfy this assertion?",
        "",
        "## Assertion",
        assertion,
        "",
        "## Answer choices",
        "- PASS: the evidence satisfies the assertion.",
        "- FAIL: the evidence contradicts or misses the assertion.",
        "- SKIP: you cannot determine the answer from the evidence.",
        "",
        `Full evidence file: ${evidencePath}`,
        `Full consolidated review: ${join(skillDir, "LAST_REVIEW.md")}`,
        "",
        "---",
        "",
        evidenceText,
      ].join("\n");
      await ctx.ui.editor(
        `Question: assertion ${index + 1}/${evalResult.assertions.length}`,
        question,
      );
      const choice = await ctx.ui.select(
        `Does assertion ${index + 1}/${evalResult.assertions.length} pass?`,
        ASSERTION_LABELS,
      );
      if (choice) {
        verdict.assertions.push({ text: assertion, verdict: ASSERTION_TO_VERDICT[choice] });
      }
    }

    // Grade manual review items.
    for (const [index, item] of evalResult.manual_review.entries()) {
      const question = [
        `# Manual Review ${index + 1}/${evalResult.manual_review.length}: ${evalResult.eval_id}`,
        "",
        "## Question",
        "Does this manual review item look OK, or does it reveal an issue?",
        "",
        "## Manual review item",
        item,
        "",
        "## Answer choices",
        "- OK: the evidence looks acceptable for this item.",
        "- Issue found: the evidence reveals a problem to address.",
        "- SKIP: you cannot determine the answer from the evidence.",
        "",
        `Full evidence file: ${evidencePath}`,
        `Full consolidated review: ${join(skillDir, "LAST_REVIEW.md")}`,
        "",
        "---",
        "",
        evidenceText,
      ].join("\n");
      await ctx.ui.editor(
        `Question: manual review ${index + 1}/${evalResult.manual_review.length}`,
        question,
      );
      const choice = await ctx.ui.select(
        `Is manual review item ${index + 1}/${evalResult.manual_review.length} OK?`,
        REVIEW_LABELS,
      );
      if (choice) {
        verdict.manual_review.push({ text: item, verdict: REVIEW_TO_VERDICT[choice] });
      }
    }

    // Optional free-text evidence notes for this eval
    const notes = await ctx.ui.input(
      "Evidence notes (optional — Enter to skip)",
      "Any observations about output, behavior, or discrepancies...",
    );
    if (notes?.trim()) {
      verdict.notes = notes.trim();
    }

    verdicts.push(verdict);
  }

  // Save verdicts under the run directory (not global skill dir)
  const verdictPath = join(runDir, "review-verdicts.json");
  writeFileSync(verdictPath, JSON.stringify(verdicts, null, 2) + "\n", "utf-8");

  // Summary
  const totalAssertions = verdicts.reduce(
    (sum, v) => sum + v.assertions.length + v.manual_review.length,
    0,
  );
  const passed = verdicts.reduce(
    (sum, v) =>
      sum +
      v.assertions.filter((a) => a.verdict === "PASS").length +
      v.manual_review.filter((m) => m.verdict === "OK").length,
    0,
  );
  const failed = verdicts.reduce(
    (sum, v) =>
      sum +
      v.assertions.filter((a) => a.verdict === "FAIL").length +
      v.manual_review.filter((m) => m.verdict === "ISSUE").length,
    0,
  );

  await ctx.ui.confirm(
    "Review Complete",
    [
      `✅ ${passed} passed`,
      `❌ ${failed} failed`,
      `⏭️ ${totalAssertions - passed - failed} skipped`,
      "",
      `Verdicts saved to: ${verdictPath}`,
      `Full review: LAST_REVIEW.md`,
    ].join("\n"),
  );
}

// ── Build the improvement message for the agent ───────────────────

function buildImprovementMessage(
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
    `\`\`\`bash`,
    `python3 ${scriptPath("test-skill.py")} ${skillDir}`,
    `\`\`\``,
    "If the static gate has errors, fix them before proceeding. If evals are missing or have placeholders, scaffold them with:",
    `\`\`\`bash`,
    `python3 ${scriptPath("test-skill.py")} ${skillDir} --create-evals`,
    `\`\`\``,
    "Then replace all placeholder text before running evals.",
    "",
    "### Phase 2: Edit",
    "",
    "Make evidence-driven changes to SKILL.md. Add observed corrections to Gotchas, fix the description boundary, adjust references. Run the static gate again after editing.",
    "",
    "### Phase 3: Evaluate",
    "",
    "Run evals and LLM judge in a single command:",
    `\`\`\`bash`,
    `python3 ${scriptPath("run-skill-evals.py")} ${skillDir} --mode all --llm-judge`,
    `\`\`\``,
    "This produces a run directory under `evals/runs/<timestamp>/`. Note the exact timestamp.",
    "Then consolidate results with that timestamp:",
    `\`\`\`bash`,
    `python3 ${scriptPath("consolidate-review.py")} ${skillDir}/evals/runs/<timestamp> --link-to ${skillDir}/LAST_REVIEW.md`,
    `\`\`\``,
    "",
    "### Phase 4: Hand off to human",
    "",
    "When evaluation and consolidation are done, call `skill_review_human_handoff` with both the skill path AND the exact run directory path. Do NOT edit the skill further after calling this tool — wait for human feedback.",
    "",
    `Call: \`skill_review_human_handoff\` with \`skillDir: "${skillDir}"\` and \`runDir: "${skillDir}/evals/runs/<timestamp>"\``,
  );

  return parts.join("\n");
}

// ── Extension ─────────────────────────────────────────────────────

export default function (pi: ExtensionAPI) {
  // ── Tool: handoff from agent to interactive human review ──────

  pi.registerTool({
    name: "skill_review_human_handoff",
    label: "Skill Review Handoff",
    description:
      "Call this tool when you have completed the Evaluate phase (ran evals, LLM judge, and consolidation) and are ready for the human to review the results interactively. Pass the path to the skill directory AND the exact eval run directory. The interactive review TUI starts immediately.",
    parameters: Type.Object({
      skillDir: Type.String({
        description: "Absolute path to the skill directory being reviewed",
      }),
      runDir: Type.Optional(
        Type.String({
          description:
            "Absolute path to the eval run directory (evals/runs/<timestamp>). If omitted, the lexicographically latest run directory is used.",
        }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      if (!ctx.hasUI) {
        return {
          content: [
            {
              type: "text",
              text: "Interactive human review is not available in non-interactive mode (--print, --mode json, RPC without UI). Please run pi interactively to review eval results.",
            },
          ],
          details: {},
        };
      }

      const skillDir = params.skillDir;
      const runDir = params.runDir ?? findLatestRunDir(skillDir);

      if (!runDir) {
        return {
          content: [
            {
              type: "text",
              text: `No eval run directory found under ${skillDir}/evals/runs/. Run evals and consolidation with the scripts before calling this tool.`,
            },
          ],
          details: {},
        };
      }

      const report = loadReport(runDir);
      if (!report) {
        return {
          content: [
            {
              type: "text",
              text: `No report.json found in ${runDir}. Run the eval scripts first.`,
            },
          ],
          details: {},
        };
      }

      // Run the interactive TUI review directly. This pauses the agent turn
      // while the human grades assertions and manual review items.
      await interactiveReview(ctx, report, skillDir, runDir);

      return {
        content: [
          {
            type: "text",
            text: "Interactive human review completed. Verdicts saved to the eval run directory. See LAST_REVIEW.md for the full consolidated review. The human may now provide feedback for further iterations.",
          },
        ],
        details: {},
        terminate: true,
      };
    },
  });

  // ── Command: /skill-review — agent-driven improvement ──────────

  pi.registerCommand("skill-review", {
    description:
      "Improve a skill using the skill-creation methodology — sends the full workflow to the agent",
    handler: async (args, ctx) => {
      let skillDir = args?.trim() || "";

      // Expand ~ and resolve relative paths
      if (skillDir) {
        if (skillDir.startsWith("~")) {
          skillDir = join(homedir(), skillDir.slice(1));
        } else if (!skillDir.startsWith("/")) {
          skillDir = join(ctx.cwd, skillDir);
        }
      }

      if (!skillDir && ctx.hasUI) {
        const skills = discoverSkills(ctx.cwd);
        if (skills.length === 0) {
          ctx.ui.notify(
            "No skills found in ~/.pi/agent/skills/, ~/.agents/skills/, .pi/skills/, or .agents/skills/",
            "error",
          );
          return;
        }

        // Build string labels and a lookup map for disambiguation.
        // ctx.ui.select only accepts string[], so {value,label} objects
        // would render as "[object Object]" at runtime.
        const labelToPath = new Map<string, string>();
        const skillLabels = skills.map((p) => {
          const name = basename(p);
          const dupCount = skills.filter((s) => basename(s) === name).length;
          let label: string;
          if (dupCount > 1) {
            label = `${name} (${basename(join(p, ".."))})`;
          } else {
            label = name;
          }
          // Guard against pathological collisions (same name + same parent)
          if (labelToPath.has(label)) {
            label = `${label} [${p}]`;
          }
          labelToPath.set(label, p);
          return label;
        });
        const chosenLabel = await ctx.ui.select(
          "Pick a skill to improve:",
          skillLabels,
        );
        if (!chosenLabel) {
          ctx.ui.notify("Cancelled", "warning");
          return;
        }
        skillDir = labelToPath.get(chosenLabel)!;
      }

      if (!skillDir || !existsSync(join(skillDir, "SKILL.md"))) {
        ctx.ui.notify(
          `Not a valid skill directory (no SKILL.md): ${skillDir}`,
          "error",
        );
        return;
      }

      if (!existsSync(join(SKILL_CREATION_DIR, "SKILL.md"))) {
        ctx.ui.notify(
          `Skill-creation skill not found at ${SKILL_CREATION_DIR}`,
          "error",
        );
        return;
      }

      if (!existsSync(scriptPath("test-skill.py"))) {
        ctx.ui.notify(
          `Skill-creation scripts not found at ${SKILL_CREATION_DIR}/scripts/`,
          "error",
        );
        return;
      }

      // Confirm before launching the potentially expensive workflow
      const confirmed = await ctx.ui.confirm(
        "Launch skill improvement?",
        `This will trigger an agent turn that runs multiple eval passes and may be expensive.\n\nSkill: ${basename(skillDir)}\nPath: ${skillDir}\n\nContinue?`,
      );
      if (!confirmed) {
        ctx.ui.notify("Cancelled", "warning");
        return;
      }

      const message = buildImprovementMessage(
        skillDir,
        SKILL_CREATION_DIR,
      );

      if (!ctx.isIdle()) {
        await ctx.waitForIdle();
      }
      pi.sendUserMessage(message);

      ctx.ui.notify(
        `Improvement workflow sent for ${basename(skillDir)}. The agent will work through Assess → Edit → Evaluate, then hand off to the interactive human review TUI.`,
        "info",
      );
    },
  });
}
