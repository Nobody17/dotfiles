import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { safeReadFile } from "./paths";
import type { EvalReport } from "./report";

// ── Helpers ────────────────────────────────────────────────────────

function safeFileSegment(value: string): string {
  return value.replace(/[^a-zA-Z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "eval";
}

function fencedBlock(language: string, content: string): string {
  let longestRun = 0;
  let currentRun = 0;
  for (const character of content) {
    if (character === "`") {
      currentRun++;
      longestRun = Math.max(longestRun, currentRun);
    } else {
      currentRun = 0;
    }
  }
  const fence = "`".repeat(Math.max(3, longestRun + 1));
  return `${fence}${language}\n${content}\n${fence}`;
}

// ── Evidence building ──────────────────────────────────────────────

function buildEvidenceMarkdown(
  evalResult: EvalReport["output_results"][number],
): string {
  const lines: string[] = [
    `**Eval:** ${evalResult.eval_id}`,
    "",
    "**Prompt:**",
    evalResult.prompt,
  ];

  if (evalResult.expected_output) {
    lines.push("", "**Expected:**", evalResult.expected_output);
  }

  if (evalResult.assertions.length > 0 || evalResult.manual_review.length > 0) {
    lines.push("", "**Questions to answer:**");
  }

  if (evalResult.assertions.length > 0) {
    lines.push(
      "",
      "Assertions:",
      ...evalResult.assertions.map(
        (a) => `- Does the output satisfy this assertion? ${a}`,
      ),
    );
  }

  if (evalResult.manual_review.length > 0) {
    lines.push(
      "",
      "Manual review:",
      ...evalResult.manual_review.map(
        (item) =>
          `- Does this manual review item look OK, or does it reveal an issue? ${item}`,
      ),
    );
  }

  // Per-variant outputs
  if (evalResult.variants && evalResult.variants.length > 0) {
    for (const variant of evalResult.variants) {
      lines.push("", `── ${variant.variant} (run ${variant.run_number}) ──`);
      const cr = variant.command_result;
      if (cr) {
        lines.push(
          `Return code: ${cr.returncode ?? "?"} | Timed out: ${cr.timed_out} | ${variant.activated_skill ? "[SKILL RUN]" : "[BASELINE — no skill]"}`,
        );
        // Changed files summary
        if (variant.changed_files) {
          const entries = Object.entries(variant.changed_files).filter(
            ([, v]) => Array.isArray(v) && v.length > 0,
          );
          if (entries.length > 0) {
            lines.push(
              "Changed files:\n" +
                entries
                  .map(([k, v]) => `  ${k}: ${v.join(", ")}`)
                  .join("\n"),
            );
          }
        }
        const stdout = safeReadFile(cr.stdout_path);
        if (stdout) lines.push("stdout:", fencedBlock("text", stdout));
        const stderr = safeReadFile(cr.stderr_path);
        if (stderr?.trim()) lines.push("stderr:", fencedBlock("text", stderr));
      } else {
        lines.push("(no command result — may have been skipped)");
      }
    }
  }

  // LLM judge output
  if (evalResult.judge_output_path) {
    const judgeText = safeReadFile(evalResult.judge_output_path);
    if (judgeText) {
      lines.push("", "**LLM Judge:**", fencedBlock("markdown", judgeText));
    }
  }

  return lines.join("\n") + "\n";
}

function writeEvidenceFile(
  runDir: string,
  evalResult: EvalReport["output_results"][number],
  evidenceText: string,
): string {
  const evidenceDir = join(runDir, "interactive-review-evidence");
  mkdirSync(evidenceDir, { recursive: true });
  const evidencePath = join(
    evidenceDir,
    `${safeFileSegment(evalResult.eval_id)}.md`,
  );
  writeFileSync(evidencePath, evidenceText, "utf-8");
  return evidencePath;
}

// ── Verdict types ──────────────────────────────────────────────────

interface VerdictItem {
  text: string;
  verdict: string;
}

interface Verdict {
  eval_id: string;
  assertions: VerdictItem[];
  manual_review: VerdictItem[];
  notes?: string;
}

// ── Review group config ────────────────────────────────────────────

interface ReviewGroupConfig {
  key: "assertions" | "manual_review";
  title: string;
  questionTemplate: string;
  labels: string[];
  verdictMap: Record<string, string>;
}

const ASSERTION_GROUP: ReviewGroupConfig = {
  key: "assertions",
  title: "Assertion",
  questionTemplate: "Does the output satisfy this assertion?",
  labels: ["✅ PASS", "❌ FAIL", "⏭️ SKIP"],
  verdictMap: { "✅ PASS": "PASS", "❌ FAIL": "FAIL", "⏭️ SKIP": "SKIP" },
};

const MANUAL_REVIEW_GROUP: ReviewGroupConfig = {
  key: "manual_review",
  title: "Manual Review",
  questionTemplate:
    "Does this manual review item look OK, or does it reveal an issue?",
  labels: ["✅ OK", "❌ Issue found", "⏭️ SKIP"],
  verdictMap: { "✅ OK": "OK", "❌ Issue found": "ISSUE", "⏭️ SKIP": "SKIP" },
};

// ── Grading helpers ────────────────────────────────────────────────

async function gradeGroup(
  ctx: ExtensionContext,
  group: ReviewGroupConfig,
  items: string[],
  evalId: string,
  skillDir: string,
  evidencePath: string,
  evidenceText: string,
): Promise<VerdictItem[]> {
  const results: VerdictItem[] = [];

  for (const [index, item] of items.entries()) {
    const question = [
      `# ${group.title} ${index + 1}/${items.length}: ${evalId}`,
      "",
      "## Question",
      group.questionTemplate,
      "",
      `## ${group.title} item`,
      item,
      "",
      "## Answer choices",
      ...group.labels.map((label) => {
        const code = group.verdictMap[label];
        return `- ${label}: ${code}`;
      }),
      "",
      `Full evidence file: ${evidencePath}`,
      `Full consolidated review: ${join(skillDir, "LAST_REVIEW.md")}`,
      "",
      "---",
      "",
      evidenceText,
    ].join("\n");

    await ctx.ui.editor(
      `Question: ${group.title.toLowerCase()} ${index + 1}/${items.length}`,
      question,
    );

    const choice = await ctx.ui.select(
      `${group.title} ${index + 1}/${items.length}?`,
      group.labels,
    );

    if (choice) {
      results.push({ text: item, verdict: group.verdictMap[choice] });
    }
  }

  return results;
}

// ── Summary helpers ────────────────────────────────────────────────

interface VerdictSummary {
  passed: number;
  failed: number;
  skipped: number;
}

function summarizeVerdicts(verdicts: Verdict[]): VerdictSummary {
  let passed = 0;
  let failed = 0;
  for (const v of verdicts) {
    passed +=
      v.assertions.filter((a) => a.verdict === "PASS").length +
      v.manual_review.filter((m) => m.verdict === "OK").length;
    failed +=
      v.assertions.filter((a) => a.verdict === "FAIL").length +
      v.manual_review.filter((m) => m.verdict === "ISSUE").length;
  }
  const total = verdicts.reduce(
    (sum, v) => sum + v.assertions.length + v.manual_review.length,
    0,
  );
  return { passed, failed, skipped: total - passed - failed };
}

// ── Main review flow ───────────────────────────────────────────────

export async function interactiveReview(
  ctx: ExtensionContext,
  report: EvalReport,
  skillDir: string,
  runDir: string,
): Promise<void> {
  if (!ctx.hasUI) return;

  const verdicts: Verdict[] = [];

  // Trigger evals summary
  if (report.trigger_results.length > 0) {
    const commandFailures = report.output_summary.command_failures ?? 0;
    const warning = commandFailures > 0
      ? `\n\n⚠️ ${commandFailures} command failure(s)/timeout(s). Some eval results may be incomplete.`
      : "";

    const failList = report.trigger_results
      .filter((r) => !r.passed)
      .map((r) => `❌ ${r.query_id}: ${r.query}`)
      .join("\n");

    const proceed = await ctx.ui.confirm(
      "Trigger Evals",
      `${report.trigger_summary.passed}/${report.trigger_summary.total} trigger queries passed.${warning}\n\n${failList || "All passed!"}\n\nContinue to output evals?`,
    );
    if (!proceed) return;
  }

  // Command failure warning before grading
  if (report.output_summary.command_failures > 0) {
    const acknowledged = await ctx.ui.confirm(
      "⚠️ Command Failures",
      `${report.output_summary.command_failures} eval command(s) timed out or failed. Some output-eval results may be incomplete.`,
    );
    if (!acknowledged) return;
  }

  // Grade each output eval
  for (const evalResult of report.output_results) {
    if (!evalResult.assertions.length && !evalResult.manual_review.length) {
      continue;
    }

    const verdict: Verdict = {
      eval_id: evalResult.eval_id,
      assertions: [],
      manual_review: [],
    };

    const evidenceText = buildEvidenceMarkdown(evalResult);
    const evidencePath = writeEvidenceFile(runDir, evalResult, evidenceText);
    ctx.ui.notify(
      `Full review evidence written for ${evalResult.eval_id}: ${evidencePath}`,
      "info",
    );

    // Grade assertions and manual review items using data-driven groups
    verdict.assertions = await gradeGroup(
      ctx,
      ASSERTION_GROUP,
      evalResult.assertions,
      evalResult.eval_id,
      skillDir,
      evidencePath,
      evidenceText,
    );

    verdict.manual_review = await gradeGroup(
      ctx,
      MANUAL_REVIEW_GROUP,
      evalResult.manual_review,
      evalResult.eval_id,
      skillDir,
      evidencePath,
      evidenceText,
    );

    // Optional notes
    const notes = await ctx.ui.input(
      "Evidence notes (optional — Enter to skip)",
      "Any observations about output, behavior, or discrepancies...",
    );
    if (notes?.trim()) {
      verdict.notes = notes.trim();
    }

    verdicts.push(verdict);
  }

  // Save verdicts
  const verdictPath = join(runDir, "review-verdicts.json");
  writeFileSync(
    verdictPath,
    JSON.stringify(verdicts, null, 2) + "\n",
    "utf-8",
  );

  // Summary
  const summary = summarizeVerdicts(verdicts);
  await ctx.ui.confirm(
    "Review Complete",
    [
      `✅ ${summary.passed} passed`,
      `❌ ${summary.failed} failed`,
      `⏭️ ${summary.skipped} skipped`,
      "",
      `Verdicts saved to: ${verdictPath}`,
      `Full review: LAST_REVIEW.md`,
    ].join("\n"),
  );
}
