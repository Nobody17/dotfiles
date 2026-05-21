import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { existsSync } from "node:fs";
import { join, basename } from "node:path";
import {
  SKILL_CREATION_DIR,
  scriptPath,
  discoverSkills,
  findLatestRunDir,
  resolveSkillDir,
  buildSkillLabels,
} from "./paths";
import { loadReport } from "./report";
import { buildImprovementMessage } from "./workflow-message";
import { interactiveReview } from "./interactive-review";

// ── Result helper ──────────────────────────────────────────────────

function textResult(text: string, terminate = false) {
  return {
    content: [{ type: "text" as const, text }],
    details: {},
    terminate,
  };
}

// ── Validation ─────────────────────────────────────────────────────

function validateSkillReviewSetup(skillDir: string): string | null {
  if (!skillDir || !existsSync(join(skillDir, "SKILL.md"))) {
    return `Not a valid skill directory (no SKILL.md): ${skillDir}`;
  }
  if (!existsSync(join(SKILL_CREATION_DIR, "SKILL.md"))) {
    return `Skill-creation skill not found at ${SKILL_CREATION_DIR}`;
  }
  if (!existsSync(scriptPath("test-skill.py"))) {
    return `Skill-creation scripts not found at ${SKILL_CREATION_DIR}/scripts/`;
  }
  return null;
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
        return textResult(
          "Interactive human review is not available in non-interactive mode (--print, --mode json, RPC without UI). Please run pi interactively to review eval results.",
        );
      }

      const skillDir = params.skillDir;
      const runDir = params.runDir ?? findLatestRunDir(skillDir);

      if (!runDir) {
        return textResult(
          `No eval run directory found under ${skillDir}/evals/runs/. Run evals and consolidation with the scripts before calling this tool.`,
        );
      }

      const report = loadReport(runDir);
      if (!report) {
        return textResult(
          `No report.json found in ${runDir}. Run the eval scripts first.`,
        );
      }

      await interactiveReview(ctx, report, skillDir, runDir);

      return textResult(
        "Interactive human review completed. Verdicts saved to the eval run directory. See LAST_REVIEW.md for the full consolidated review. The human may now provide feedback for further iterations.",
        true,
      );
    },
  });

  // ── Command: /skill-review — agent-driven improvement ──────────

  pi.registerCommand("skill-review", {
    description:
      "Improve a skill using the skill-creation methodology — sends the full workflow to the agent",
    handler: async (args, ctx) => {
      // Resolve or select skill directory
      let skillDir = resolveSkillDir(args?.trim() || undefined, ctx.cwd);

      if (!skillDir && ctx.hasUI) {
        const skills = discoverSkills(ctx.cwd);
        if (skills.length === 0) {
          ctx.ui.notify(
            "No skills found in ~/.pi/agent/skills/, ~/.agents/skills/, .pi/skills/, or .agents/skills/",
            "error",
          );
          return;
        }

        const { labels, labelToPath } = buildSkillLabels(skills);
        const chosenLabel = await ctx.ui.select(
          "Pick a skill to improve:",
          labels,
        );
        if (!chosenLabel) {
          ctx.ui.notify("Cancelled", "warning");
          return;
        }
        skillDir = labelToPath.get(chosenLabel)!;
      }

      if (!skillDir) {
        ctx.ui.notify("No skill specified or selected", "error");
        return;
      }

      // Validate
      const error = validateSkillReviewSetup(skillDir);
      if (error) {
        ctx.ui.notify(error, "error");
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

      // Send the workflow prompt
      const message = buildImprovementMessage(skillDir, SKILL_CREATION_DIR);

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
