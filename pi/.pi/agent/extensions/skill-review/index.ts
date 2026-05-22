import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { existsSync } from "node:fs";
import { basename, join } from "node:path";
import {
  SKILL_CREATION_DIR,
  scriptPath,
  discoverSkills,
  findLatestRunDir,
  resolveSkillDir,
  buildSkillLabels,
  isRunDirForSkill,
  piDir,
  resolvePathArg,
} from "./paths";
import { loadReportWithDiagnostics } from "./report";
import { buildCreationMessage, buildImprovementMessage } from "./workflow-message";
import { interactiveReview, type InteractiveReviewOutcome } from "./interactive-review";
import {
  parseSkillCreateArgs,
  parseSkillReviewArgs,
  type SkillCreateCommandOptions,
  type SkillReviewCommandOptions,
} from "./args";

// ── Result helper ──────────────────────────────────────────────────

function textResult(text: string, terminate = false) {
  return {
    content: [{ type: "text" as const, text }],
    details: {},
    terminate,
  };
}

function outcomeText(outcome: InteractiveReviewOutcome): string {
  const lines: string[] = [
    outcome.cancelled ? "Interactive human review cancelled." : "Interactive human review completed.",
    `Verdicts: ${outcome.verdictPath}`,
    `Markdown: ${outcome.verdictMarkdownPath}`,
    `Summary: ${outcome.summary.passed} passed/accepted, ${outcome.summary.failed} failed/issues, ${outcome.summary.skipped} skipped.`,
  ];

  if (outcome.failedItems.length > 0) {
    lines.push("", "Failed/issue items to address:", ...outcome.failedItems.map((item) => `- ${item}`));
  }
  if (outcome.skippedItems.length > 0) {
    lines.push("", "Skipped items needing later review:", ...outcome.skippedItems.map((item) => `- ${item}`));
  }

  return lines.join("\n");
}

function commandFeedback(
  pi: ExtensionAPI,
  ctx: ExtensionContext,
  message: string,
  level: "info" | "warning" | "error" = "info",
): void {
  if (ctx.hasUI) {
    ctx.ui.notify(message, level);
    return;
  }

  pi.sendMessage({
    customType: "skill-review",
    content: message,
    display: true,
    details: { level },
  });
}

function truncateText(text: string | undefined, maxLength = 2000): string {
  if (!text) return "";
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}\n… truncated …`;
}

function execSummary(label: string, result: { code?: number | null; stdout?: string; stderr?: string; killed?: boolean }): string {
  const lines = [`${label}: exit ${result.code ?? "?"}${result.killed ? " (killed)" : ""}`];
  const stdout = truncateText(result.stdout?.trim());
  const stderr = truncateText(result.stderr?.trim());
  if (stdout) lines.push("stdout:", stdout);
  if (stderr) lines.push("stderr:", stderr);
  return lines.join("\n");
}

// ── Validation ─────────────────────────────────────────────────────

function validateSkillReviewSetup(skillDir: string): string | null {
  if (!skillDir || !existsSync(join(skillDir, "SKILL.md"))) {
    return `Not a valid skill directory (no SKILL.md): ${skillDir}`;
  }
  if (!existsSync(join(SKILL_CREATION_DIR, "SKILL.md"))) {
    return `Skill-creation skill not found at ${SKILL_CREATION_DIR}`;
  }
  for (const scriptName of ["test-skill.py", "run-skill-evals.py", "consolidate-review.py"]) {
    if (!existsSync(scriptPath(scriptName))) {
      return `Skill-creation script not found: ${scriptPath(scriptName)}`;
    }
  }
  return null;
}

function validateRunDir(
  skillDir: string,
  runDir: string,
  options: { requireReport?: boolean } = {},
): string | null {
  if (!existsSync(runDir)) return `Eval run directory does not exist: ${runDir}`;
  if (!isRunDirForSkill(runDir, skillDir)) {
    return `Eval run directory must be a direct child of ${skillDir}/evals/runs/: ${runDir}`;
  }
  if (options.requireReport && !existsSync(join(runDir, "report.json"))) {
    return `Eval run directory has no report.json: ${runDir}`;
  }
  return null;
}

async function chooseSkillDir(
  ctx: { cwd: string; hasUI: boolean; ui: { select: (prompt: string, choices: string[]) => Promise<string | undefined>; notify: (message: string, level?: "info" | "warning" | "error") => void } },
): Promise<string | null> {
  if (!ctx.hasUI) return null;

  const skills = discoverSkills(ctx.cwd);
  if (skills.length === 0) {
    ctx.ui.notify(
      "No skills found in ~/.pi/agent/skills/, ~/.agents/skills/, .pi/skills/, or .agents/skills/.",
      "error",
    );
    return null;
  }

  const { labels, labelToPath } = buildSkillLabels(skills, ctx.cwd);
  const chosenLabel = await ctx.ui.select("Pick a skill to improve:", labels);
  if (!chosenLabel) {
    ctx.ui.notify("Cancelled", "warning");
    return null;
  }
  return labelToPath.get(chosenLabel) ?? null;
}

// ── Direct runner ──────────────────────────────────────────────────

function evalArgs(skillDir: string, options: SkillReviewCommandOptions, runDir: string): string[] {
  const args = [scriptPath("run-skill-evals.py"), skillDir, "--mode", options.mode];
  if (options.triggerRuns !== undefined) args.push("--trigger-runs", String(options.triggerRuns));
  if (options.dryRun) args.push("--dry-run");
  if (!options.noLlmJudge && !options.dryRun) args.push("--llm-judge");
  if (options.resumeRunDir) args.push("--resume", options.resumeRunDir);
  else args.push("--run-dir", runDir);
  return args;
}

function createDirectRunDir(skillDir: string): string {
  const isoTimestamp = new Date().toISOString();
  const date = isoTimestamp.slice(0, 10).replace(/-/g, "");
  const time = isoTimestamp.slice(11, 19).replace(/:/g, "");
  return join(skillDir, "evals", "runs", `${date}T${time}Z-direct`);
}

async function runDirectReviewWorkflow(
  pi: ExtensionAPI,
  ctx: ExtensionContext,
  skillDir: string,
  options: SkillReviewCommandOptions,
): Promise<void> {
  commandFeedback(pi, ctx, `Running static skill gate for ${basename(skillDir)}...`, "info");
  const staticResult = await pi.exec("python3", [scriptPath("test-skill.py"), skillDir], {
    timeout: 600_000,
  });
  if (staticResult.code !== 0) {
    commandFeedback(pi, ctx, execSummary("Static gate failed", staticResult), "error");
    return;
  }

  if (options.noEvals) {
    commandFeedback(pi, ctx, execSummary("Static gate passed; evals skipped", staticResult), "info");
    return;
  }

  const runDir = options.resumeRunDir ?? createDirectRunDir(skillDir);
  commandFeedback(pi, ctx, `Running skill evals for ${basename(skillDir)}...`, "info");
  const evalResult = await pi.exec("python3", evalArgs(skillDir, options, runDir), {
    timeout: 7_200_000,
  });
  if (evalResult.code !== 0) {
    commandFeedback(pi, ctx, execSummary("Eval command returned non-zero", evalResult), "warning");
  }

  if (!existsSync(runDir)) {
    commandFeedback(pi, ctx, `No eval run directory found after running evals: ${runDir}`, "error");
    return;
  }

  const runDirError = validateRunDir(skillDir, runDir, { requireReport: true });
  if (runDirError) {
    commandFeedback(pi, ctx, runDirError, "error");
    return;
  }

  commandFeedback(pi, ctx, `Consolidating review for ${runDir}...`, "info");
  const consolidateResult = await pi.exec(
    "python3",
    [scriptPath("consolidate-review.py"), runDir, "--link-to", join(skillDir, "LAST_REVIEW.md")],
    { timeout: 600_000 },
  );
  if (consolidateResult.code !== 0) {
    commandFeedback(pi, ctx, execSummary("Consolidation failed", consolidateResult), "error");
    return;
  }

  const reportResult = loadReportWithDiagnostics(runDir);
  if (!reportResult.ok) {
    commandFeedback(pi, ctx, reportResult.error, "error");
    return;
  }

  if (options.dryRun) {
    commandFeedback(
      pi,
      ctx,
      `Direct dry run complete. Consolidated review plan: ${join(skillDir, "LAST_REVIEW.md")}. Run again without --dry-run for human verdict grading.`,
      "info",
    );
    return;
  }

  if (!ctx.hasUI) {
    commandFeedback(
      pi,
      ctx,
      `Direct review run complete. Consolidated review: ${join(skillDir, "LAST_REVIEW.md")}. Human TUI handoff is only available in interactive/RPC UI mode.`,
      "info",
    );
    return;
  }

  const outcome = await interactiveReview(ctx, reportResult.report, skillDir, runDir);
  commandFeedback(pi, ctx, outcomeText(outcome), outcome.summary.failed > 0 ? "warning" : "info");
}

// ── Creation wizard ────────────────────────────────────────────────

function normalizeSkillName(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");
}

async function collectCreationOptions(
  ctx: {
    cwd: string;
    hasUI: boolean;
    ui: {
      input: (prompt: string, placeholder?: string) => Promise<string | undefined>;
      select: (prompt: string, choices: string[]) => Promise<string | undefined>;
      editor: (prompt: string, text: string) => Promise<string | undefined>;
      confirm: (title: string, message?: string) => Promise<boolean>;
    };
  },
  initialOptions: SkillCreateCommandOptions,
): Promise<SkillCreateCommandOptions | null> {
  const options: SkillCreateCommandOptions = { ...initialOptions };

  if (!ctx.hasUI) {
    if (options.skillName) options.skillName = normalizeSkillName(options.skillName);
    if (options.targetDir) {
      options.targetDir = resolvePathArg(options.targetDir, ctx.cwd);
    } else if (options.skillName && options.scope === "project") {
      options.targetDir = join(ctx.cwd, ".pi", "skills", options.skillName);
    } else if (options.skillName && options.scope !== "custom") {
      options.targetDir = join(piDir(), "skills", options.skillName);
    }
    return options;
  }

  if (!options.skillName) {
    const skillName = await ctx.ui.input("Skill name", "release-checklist");
    if (!skillName?.trim()) return null;
    options.skillName = skillName;
  }
  options.skillName = normalizeSkillName(options.skillName);
  if (!options.skillName) return null;

  if (!options.targetDir && !options.scope) {
    const scopeChoice = await ctx.ui.select("Where should the skill be created?", [
      "Agent global (~/.pi/agent/skills)",
      "Project (.pi/skills under current cwd)",
      "Custom path",
    ]);
    if (scopeChoice === "Agent global (~/.pi/agent/skills)") options.scope = "agent";
    else if (scopeChoice === "Project (.pi/skills under current cwd)") options.scope = "project";
    else if (scopeChoice === "Custom path") options.scope = "custom";
    else return null;
  }

  if (!options.targetDir) {
    if (options.scope === "project") {
      options.targetDir = join(ctx.cwd, ".pi", "skills", options.skillName);
    } else if (options.scope === "custom") {
      const customPath = await ctx.ui.input("Target skill directory", `./skills/${options.skillName}`);
      if (!customPath?.trim()) return null;
      options.targetDir = resolvePathArg(customPath, ctx.cwd);
    } else {
      options.targetDir = join(piDir(), "skills", options.skillName);
    }
  } else {
    options.targetDir = resolvePathArg(options.targetDir, ctx.cwd);
  }

  if (!options.taskDomain) {
    options.taskDomain = await ctx.ui.input(
      "What task/domain does the skill cover?",
      "e.g. release checklist, PDF form filling, database migrations",
    );
  }

  if (!options.useCases) {
    options.useCases = await ctx.ui.editor(
      "Specific use cases the skill should handle (include core prompts, edge cases, and near-misses)",
      "",
    );
  }

  if (options.needsScripts === undefined) {
    const scriptsChoice = await ctx.ui.select("Does the skill need executable helper scripts?", [
      "No, instructions only",
      "Yes, deterministic scripts are needed",
      "Not sure — let the agent decide",
    ]);
    if (scriptsChoice === "No, instructions only") options.needsScripts = false;
    else if (scriptsChoice === "Yes, deterministic scripts are needed") options.needsScripts = true;
  }

  if (!options.referenceMaterials) {
    options.referenceMaterials = await ctx.ui.input(
      "Reference materials to include or read (optional)",
      "paths, URLs, runbooks, prior corrections...",
    );
  }

  if (existsSync(options.targetDir)) {
    const confirmed = await ctx.ui.confirm(
      "Target exists",
      `${options.targetDir} already exists. Continue and let the agent inspect before editing?`,
    );
    if (!confirmed) return null;
  }

  return options;
}

// ── Extension ─────────────────────────────────────────────────────

export default function (pi: ExtensionAPI) {
  // ── Tool: handoff from agent to interactive human review ──────

  pi.registerTool({
    name: "skill_review_human_handoff",
    label: "Skill Review Handoff",
    description:
      "Call this tool when you have completed the Evaluate phase (ran evals, LLM judge, and consolidation) and are ready for the human to review the results interactively. Pass the path to the skill directory and the exact eval run directory. If runDir is omitted, the user must confirm the latest run before the TUI starts.",
    parameters: Type.Object({
      skillDir: Type.String({
        description: "Absolute path to the skill directory being reviewed",
      }),
      runDir: Type.Optional(
        Type.String({
          description:
            "Absolute path to the eval run directory (evals/runs/<timestamp>). If omitted, the lexicographically latest run directory is used after confirmation.",
        }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      if (!ctx.hasUI) {
        return textResult(
          "Interactive human review is not available in non-interactive mode (--print, --mode json, RPC without UI). Please run pi interactively to review eval results.",
        );
      }

      const skillDir = params.skillDir;
      let runDir = params.runDir?.trim() || undefined;
      if (!runDir) {
        runDir = findLatestRunDir(skillDir) ?? undefined;
        if (!runDir) {
          return textResult(
            `No eval run directory found under ${skillDir}/evals/runs/. Run evals and consolidation before calling this tool.`,
          );
        }
        const confirmed = await ctx.ui.confirm(
          "Use latest eval run?",
          `No runDir was provided. Use latest run?\n\n${runDir}`,
        );
        if (!confirmed) return textResult("Cancelled human review handoff.");
      }

      const setupError = validateSkillReviewSetup(skillDir);
      if (setupError) return textResult(setupError);

      const runDirError = validateRunDir(skillDir, runDir, { requireReport: true });
      if (runDirError) return textResult(runDirError);

      const reportResult = loadReportWithDiagnostics(runDir);
      if (!reportResult.ok) return textResult(reportResult.error);

      const outcome = await interactiveReview(ctx, reportResult.report, skillDir, runDir);
      return textResult(outcomeText(outcome));
    },
  });

  // ── Command: /skill-review — agent-driven or direct improvement ──

  pi.registerCommand("skill-review", {
    description:
      "Improve or evaluate a skill. Options: --quick, --full, --dry-run, --no-evals, --trigger-runs N, --direct, --mode all|trigger|output",
    handler: async (args, ctx) => {
      const parsedArgs = parseSkillReviewArgs(args);
      if (parsedArgs.errors.length > 0) {
        commandFeedback(pi, ctx, parsedArgs.errors.join("\n"), "error");
        return;
      }

      let skillDir = resolveSkillDir(parsedArgs.options.skillArgument, ctx.cwd);
      if (!skillDir) skillDir = await chooseSkillDir(ctx);

      if (!skillDir) {
        commandFeedback(
          pi,
          ctx,
          "No skill specified. Usage: /skill-review [--quick|--full|--direct|--dry-run|--no-evals] /path/to/skill",
          "error",
        );
        return;
      }

      const setupError = validateSkillReviewSetup(skillDir);
      if (setupError) {
        commandFeedback(pi, ctx, setupError, "error");
        return;
      }

      if (parsedArgs.options.resumeRunDir) {
        parsedArgs.options.resumeRunDir = resolvePathArg(parsedArgs.options.resumeRunDir, ctx.cwd);
        const runDirError = validateRunDir(skillDir, parsedArgs.options.resumeRunDir);
        if (runDirError) {
          commandFeedback(pi, ctx, runDirError, "error");
          return;
        }
      }

      if (ctx.hasUI) {
        const confirmed = await ctx.ui.confirm(
          parsedArgs.options.direct ? "Run direct skill evaluation?" : "Launch skill improvement?",
          `${parsedArgs.options.direct ? "This will run static/eval scripts from the extension." : "This will trigger an agent turn that may run evals and edit files."}\n\nSkill: ${basename(skillDir)}\nPath: ${skillDir}\n\nContinue?`,
        );
        if (!confirmed) {
          commandFeedback(pi, ctx, "Cancelled", "warning");
          return;
        }
      }

      if (parsedArgs.options.direct) {
        await runDirectReviewWorkflow(pi, ctx, skillDir, parsedArgs.options);
        return;
      }

      const message = buildImprovementMessage(skillDir, SKILL_CREATION_DIR, parsedArgs.options);

      if (!ctx.isIdle()) await ctx.waitForIdle();
      pi.sendUserMessage(message);

      commandFeedback(
        pi,
        ctx,
        `Improvement workflow sent for ${basename(skillDir)}. The agent will work through Assess → Edit → Evaluate, then hand off to the interactive human review TUI when evals run.`,
        "info",
      );
    },
  });

  // ── Command: /skill-create — guided new skill creation ───────────

  pi.registerCommand("skill-create", {
    description:
      "Create a new skill using an interactive requirements wizard and the skill-creation methodology",
    handler: async (args, ctx) => {
      const parsedArgs = parseSkillCreateArgs(args);
      if (parsedArgs.errors.length > 0) {
        commandFeedback(pi, ctx, parsedArgs.errors.join("\n"), "error");
        return;
      }

      const creationOptions = await collectCreationOptions(ctx, parsedArgs.options);
      if (!creationOptions) {
        commandFeedback(pi, ctx, "Cancelled", "warning");
        return;
      }

      if (!creationOptions.skillName && !ctx.hasUI) {
        commandFeedback(
          pi,
          ctx,
          "No skill name specified. Usage: /skill-create skill-name [--project|--global|--dir PATH] [--domain TEXT] [--use-cases TEXT]",
          "error",
        );
        return;
      }

      if (ctx.hasUI) {
        const confirmed = await ctx.ui.confirm(
          "Launch skill creation?",
          `Skill: ${creationOptions.skillName ?? "(agent will ask)"}\nTarget: ${creationOptions.targetDir ?? "(agent will decide)"}\n\nContinue?`,
        );
        if (!confirmed) {
          commandFeedback(pi, ctx, "Cancelled", "warning");
          return;
        }
      }

      const message = buildCreationMessage(SKILL_CREATION_DIR, creationOptions);
      if (!ctx.isIdle()) await ctx.waitForIdle();
      pi.sendUserMessage(message);
      commandFeedback(pi, ctx, `Skill creation workflow sent for ${creationOptions.skillName ?? "new skill"}.`, "info");
    },
  });
}
