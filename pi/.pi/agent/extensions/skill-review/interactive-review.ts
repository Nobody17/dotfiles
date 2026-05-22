import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
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

function commandResultLines(commandResult: EvalReport["output_results"][number]["variants"][number]["command_result"]): string[] {
  if (!commandResult) return ["(no command result — may have been skipped)"];
  const lines: string[] = [
    `Return code: ${commandResult.returncode ?? "?"} | Timed out: ${commandResult.timed_out}`,
  ];
  if (commandResult.command?.length) lines.push(`Command: ${commandResult.command.join(" ")}`);
  if (commandResult.session_paths?.length) {
    lines.push("Session logs:", ...commandResult.session_paths.map((sessionPath) => `- ${sessionPath}`));
  }
  const stdout = safeReadFile(commandResult.stdout_path);
  if (stdout) lines.push("stdout:", fencedBlock("text", stdout));
  const stderr = safeReadFile(commandResult.stderr_path);
  if (stderr?.trim()) lines.push("stderr:", fencedBlock("text", stderr));
  return lines;
}

// ── Evidence building ──────────────────────────────────────────────

function buildOutputEvidenceMarkdown(
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
        (assertion) => `- Does the output satisfy this assertion? ${assertion}`,
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

  if (evalResult.missing_files?.length) {
    lines.push("", "Missing fixture files:", ...evalResult.missing_files.map((filePath) => `- ${filePath}`));
  }

  if (evalResult.skipped_reason) {
    lines.push("", `Skipped reason: ${evalResult.skipped_reason}`);
  }

  if (evalResult.variants && evalResult.variants.length > 0) {
    for (const variant of evalResult.variants) {
      lines.push("", `── ${variant.variant} (run ${variant.run_number}) ──`);
      lines.push(variant.activated_skill ? "[SKILL RUN]" : "[BASELINE — no skill]");
      if (variant.workspace_dir) lines.push(`Workspace: ${variant.workspace_dir}`);
      if (variant.activation_evidence?.length) {
        lines.push("Activation evidence:", ...variant.activation_evidence.map((evidence) => `- ${evidence}`));
      }
      if (variant.changed_files) {
        const entries = Object.entries(variant.changed_files).filter(
          ([, changedFiles]) => Array.isArray(changedFiles) && changedFiles.length > 0,
        );
        if (entries.length > 0) {
          lines.push(
            "Changed files:\n" +
              entries
                .map(([changeType, changedFiles]) => `  ${changeType}: ${changedFiles.join(", ")}`)
                .join("\n"),
          );
        }
      }
      lines.push(...commandResultLines(variant.command_result));
    }
  }

  if (evalResult.judge_output_path) {
    const judgeText = safeReadFile(evalResult.judge_output_path);
    if (judgeText) {
      lines.push("", "**LLM Judge:**", fencedBlock("markdown", judgeText));
    }
  }

  return lines.join("\n") + "\n";
}

function buildTriggerEvidenceMarkdown(
  triggerResult: EvalReport["trigger_results"][number],
): string {
  const expected = triggerResult.should_trigger ? "SHOULD trigger" : "SHOULD NOT trigger";
  const lines: string[] = [
    `**Trigger query:** ${triggerResult.query_id}`,
    "",
    `**Expected:** ${expected}`,
    `**Observed trigger rate:** ${triggerResult.trigger_rate}`,
    `**Passed automated check:** ${triggerResult.passed}`,
    "",
    "**Prompt:**",
    triggerResult.query,
  ];

  if (triggerResult.rationale) {
    lines.push("", "**Rationale:**", triggerResult.rationale);
  }

  for (const runResult of triggerResult.runs) {
    lines.push(
      "",
      `── run ${runResult.run_number} ──`,
      `Triggered: ${runResult.triggered} | Passed: ${runResult.passed}`,
      `Run dir: ${runResult.run_dir}`,
    );
    if (runResult.skipped_reason) lines.push(`Skipped reason: ${runResult.skipped_reason}`);
    if (runResult.activation_evidence?.length) {
      lines.push("Activation evidence:", ...runResult.activation_evidence.map((evidence) => `- ${evidence}`));
    }
    lines.push(...commandResultLines(runResult.command_result));
  }

  return lines.join("\n") + "\n";
}

function writeEvidenceFile(runDir: string, fileName: string, evidenceText: string): string {
  const evidenceDir = join(runDir, "interactive-review-evidence");
  mkdirSync(evidenceDir, { recursive: true });
  const evidencePath = join(evidenceDir, `${safeFileSegment(fileName)}.md`);
  writeFileSync(evidencePath, evidenceText, "utf-8");
  return evidencePath;
}

// ── Verdict types ──────────────────────────────────────────────────

interface VerdictItem {
  text: string;
  verdict: string;
}

interface OutputVerdict {
  eval_id: string;
  assertions: VerdictItem[];
  manual_review: VerdictItem[];
  notes?: string;
}

interface TriggerVerdict {
  query_id: string;
  query: string;
  should_trigger: boolean;
  trigger_rate: number;
  verdict: string;
  notes?: string;
}

interface StoredVerdicts {
  schema_version: 2;
  saved_at: string;
  trigger_results: TriggerVerdict[];
  output_results: OutputVerdict[];
}

export interface VerdictSummary {
  passed: number;
  failed: number;
  skipped: number;
}

export interface InteractiveReviewOutcome {
  verdictPath: string;
  verdictMarkdownPath: string;
  summary: VerdictSummary;
  failedItems: string[];
  skippedItems: string[];
  cancelled: boolean;
}

function emptyStoredVerdicts(): StoredVerdicts {
  return {
    schema_version: 2,
    saved_at: new Date().toISOString(),
    trigger_results: [],
    output_results: [],
  };
}

function parseStoredVerdicts(rawValue: unknown): StoredVerdicts | null {
  if (Array.isArray(rawValue)) {
    return {
      ...emptyStoredVerdicts(),
      output_results: rawValue as OutputVerdict[],
    };
  }
  if (!rawValue || typeof rawValue !== "object") return null;
  const candidate = rawValue as Partial<StoredVerdicts>;
  return {
    ...emptyStoredVerdicts(),
    trigger_results: Array.isArray(candidate.trigger_results) ? candidate.trigger_results : [],
    output_results: Array.isArray(candidate.output_results) ? candidate.output_results : [],
  };
}

function loadExistingVerdicts(runDir: string): StoredVerdicts | null {
  const verdictPath = join(runDir, "review-verdicts.json");
  if (!existsSync(verdictPath)) return null;
  try {
    return parseStoredVerdicts(JSON.parse(readFileSync(verdictPath, "utf-8")));
  } catch {
    return null;
  }
}

function hasAnyVerdicts(verdicts: StoredVerdicts | null): boolean {
  if (!verdicts) return false;
  if (verdicts.trigger_results.length > 0) return true;
  return verdicts.output_results.some(
    (outputVerdict) =>
      outputVerdict.assertions.length > 0 ||
      outputVerdict.manual_review.length > 0 ||
      Boolean(outputVerdict.notes),
  );
}

// ── Review group config ────────────────────────────────────────────

interface ReviewGroupConfig {
  key: "assertions" | "manual_review";
  title: string;
  questionTemplate: string;
  selectPrompt: (index: number, total: number) => string;
  labels: string[];
  verdictMap: Record<string, string>;
  positiveVerdict: string;
  negativeVerdict: string;
  skipVerdict: string;
}

const ASSERTION_GROUP: ReviewGroupConfig = {
  key: "assertions",
  title: "Assertion",
  questionTemplate: "Does the output satisfy this assertion?",
  selectPrompt: (index, total) => `Does assertion ${index}/${total} pass?`,
  labels: ["✅ PASS", "❌ FAIL", "⏭️ SKIP"],
  verdictMap: { "✅ PASS": "PASS", "❌ FAIL": "FAIL", "⏭️ SKIP": "SKIP" },
  positiveVerdict: "PASS",
  negativeVerdict: "FAIL",
  skipVerdict: "SKIP",
};

const MANUAL_REVIEW_GROUP: ReviewGroupConfig = {
  key: "manual_review",
  title: "Manual Review",
  questionTemplate:
    "Does this manual review item look OK, or does it reveal an issue?",
  selectPrompt: (index, total) =>
    `Is manual review item ${index}/${total} OK?`,
  labels: ["✅ OK", "❌ Issue found", "⏭️ SKIP"],
  verdictMap: { "✅ OK": "OK", "❌ Issue found": "ISSUE", "⏭️ SKIP": "SKIP" },
  positiveVerdict: "OK",
  negativeVerdict: "ISSUE",
  skipVerdict: "SKIP",
};

// ── Grading helpers ────────────────────────────────────────────────

async function gradeGroup(
  ctx: ExtensionContext,
  group: ReviewGroupConfig,
  items: string[],
  existingItems: VerdictItem[],
  evalId: string,
  skillDir: string,
  evidencePath: string,
  evidenceText: string,
): Promise<VerdictItem[]> {
  const resultByText = new Map(existingItems.map((item) => [item.text, item]));
  const unresolvedItems = items.filter((item) => !resultByText.has(item));

  if (unresolvedItems.length > 1) {
    const batchChoices = [
      "Review individually",
      `✅ Mark all ${group.positiveVerdict}`,
      `❌ Mark all ${group.negativeVerdict}`,
      `⏭️ Mark all ${group.skipVerdict}`,
    ];
    const batchChoice = await ctx.ui.select(
      `${group.title}: batch action for ${unresolvedItems.length} unreviewed item(s)?`,
      batchChoices,
    );
    if (batchChoice === batchChoices[1]) {
      for (const item of unresolvedItems) resultByText.set(item, { text: item, verdict: group.positiveVerdict });
    } else if (batchChoice === batchChoices[2]) {
      for (const item of unresolvedItems) resultByText.set(item, { text: item, verdict: group.negativeVerdict });
    } else if (batchChoice === batchChoices[3] || batchChoice === undefined) {
      for (const item of unresolvedItems) resultByText.set(item, { text: item, verdict: group.skipVerdict });
    }
  }

  for (const [itemIndex, item] of unresolvedItems.entries()) {
    if (resultByText.has(item)) continue;

    const question = [
      `# ${group.title} ${itemIndex + 1}/${unresolvedItems.length}: ${evalId}`,
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
      `Question: ${group.title.toLowerCase()} ${itemIndex + 1}/${unresolvedItems.length}`,
      question,
    );

    const choice = await ctx.ui.select(
      group.selectPrompt(itemIndex + 1, unresolvedItems.length),
      group.labels,
    );

    resultByText.set(item, {
      text: item,
      verdict: choice ? group.verdictMap[choice] : group.skipVerdict,
    });
  }

  return items
    .map((item) => resultByText.get(item))
    .filter((item): item is VerdictItem => Boolean(item));
}

async function gradeTriggerFailures(
  ctx: ExtensionContext,
  report: EvalReport,
  existingTriggers: TriggerVerdict[],
  runDir: string,
  skillDir: string,
): Promise<TriggerVerdict[]> {
  const resultByQueryId = new Map(existingTriggers.map((verdict) => [verdict.query_id, verdict]));
  const failedTriggers = report.trigger_results.filter((triggerResult) => !triggerResult.passed);
  const unresolvedTriggers = failedTriggers.filter(
    (triggerResult) => !resultByQueryId.has(triggerResult.query_id),
  );

  if (unresolvedTriggers.length > 1) {
    const batchChoices = [
      "Review individually",
      "✅ Accept all as benign/expected",
      "❌ Mark all as boundary issues",
      "⏭️ Skip all",
    ];
    const batchChoice = await ctx.ui.select(
      `Trigger failures: batch action for ${unresolvedTriggers.length} unreviewed item(s)?`,
      batchChoices,
    );
    if (batchChoice !== batchChoices[0]) {
      const verdict = batchChoice === batchChoices[1] ? "PASS" : batchChoice === batchChoices[2] ? "FAIL" : "SKIP";
      for (const triggerResult of unresolvedTriggers) {
        resultByQueryId.set(triggerResult.query_id, {
          query_id: triggerResult.query_id,
          query: triggerResult.query,
          should_trigger: triggerResult.should_trigger,
          trigger_rate: triggerResult.trigger_rate,
          verdict,
        });
      }
    }
  }

  for (const [triggerIndex, triggerResult] of unresolvedTriggers.entries()) {
    if (resultByQueryId.has(triggerResult.query_id)) continue;

    const evidenceText = buildTriggerEvidenceMarkdown(triggerResult);
    const evidencePath = writeEvidenceFile(
      runDir,
      `trigger-${triggerResult.query_id}`,
      evidenceText,
    );
    const direction = triggerResult.should_trigger
      ? "This is a false negative candidate: should the description be broadened?"
      : "This is a false positive candidate: should the description be narrowed?";

    const question = [
      `# Trigger Failure ${triggerIndex + 1}/${unresolvedTriggers.length}: ${triggerResult.query_id}`,
      "",
      direction,
      "",
      "Answer choices:",
      "- ✅ Accept: benign/expected edge case",
      "- ❌ Boundary issue: should drive a skill description/eval change",
      "- ⏭️ SKIP: not enough evidence",
      "",
      `Full evidence file: ${evidencePath}`,
      `Full consolidated review: ${join(skillDir, "LAST_REVIEW.md")}`,
      "",
      "---",
      "",
      evidenceText,
    ].join("\n");

    await ctx.ui.editor(
      `Question: trigger failure ${triggerIndex + 1}/${unresolvedTriggers.length}`,
      question,
    );

    const choice = await ctx.ui.select("How should this trigger failure be classified?", [
      "✅ Accept",
      "❌ Boundary issue",
      "⏭️ SKIP",
    ]);
    const notes = choice
      ? await ctx.ui.input(
          "Trigger notes (optional — Enter to skip)",
          "Any context about why this trigger result is acceptable or problematic...",
        )
      : undefined;

    resultByQueryId.set(triggerResult.query_id, {
      query_id: triggerResult.query_id,
      query: triggerResult.query,
      should_trigger: triggerResult.should_trigger,
      trigger_rate: triggerResult.trigger_rate,
      verdict: choice === "✅ Accept" ? "PASS" : choice === "❌ Boundary issue" ? "FAIL" : "SKIP",
      notes: notes?.trim() || undefined,
    });
  }

  return failedTriggers
    .map((triggerResult) => resultByQueryId.get(triggerResult.query_id))
    .filter((verdict): verdict is TriggerVerdict => Boolean(verdict));
}

// ── Summary helpers ────────────────────────────────────────────────

function summarizeVerdicts(verdicts: StoredVerdicts): VerdictSummary {
  let passed = 0;
  let failed = 0;
  let skipped = 0;

  for (const triggerVerdict of verdicts.trigger_results) {
    if (triggerVerdict.verdict === "PASS") passed++;
    else if (triggerVerdict.verdict === "FAIL") failed++;
    else skipped++;
  }

  for (const outputVerdict of verdicts.output_results) {
    const allItems = [...outputVerdict.assertions, ...outputVerdict.manual_review];
    for (const item of allItems) {
      if (item.verdict === "PASS" || item.verdict === "OK") passed++;
      else if (item.verdict === "FAIL" || item.verdict === "ISSUE") failed++;
      else skipped++;
    }
  }

  return { passed, failed, skipped };
}

function collectFailedItems(verdicts: StoredVerdicts): string[] {
  const failedItems: string[] = [];
  for (const triggerVerdict of verdicts.trigger_results) {
    if (triggerVerdict.verdict === "FAIL") {
      failedItems.push(`Trigger ${triggerVerdict.query_id}: ${triggerVerdict.query}`);
    }
  }
  for (const outputVerdict of verdicts.output_results) {
    for (const assertion of outputVerdict.assertions) {
      if (assertion.verdict === "FAIL") failedItems.push(`${outputVerdict.eval_id} assertion: ${assertion.text}`);
    }
    for (const manualItem of outputVerdict.manual_review) {
      if (manualItem.verdict === "ISSUE") failedItems.push(`${outputVerdict.eval_id} manual review: ${manualItem.text}`);
    }
  }
  return failedItems;
}

function collectSkippedItems(verdicts: StoredVerdicts): string[] {
  const skippedItems: string[] = [];
  for (const triggerVerdict of verdicts.trigger_results) {
    if (triggerVerdict.verdict === "SKIP") skippedItems.push(`Trigger ${triggerVerdict.query_id}: ${triggerVerdict.query}`);
  }
  for (const outputVerdict of verdicts.output_results) {
    for (const assertion of outputVerdict.assertions) {
      if (assertion.verdict === "SKIP") skippedItems.push(`${outputVerdict.eval_id} assertion: ${assertion.text}`);
    }
    for (const manualItem of outputVerdict.manual_review) {
      if (manualItem.verdict === "SKIP") skippedItems.push(`${outputVerdict.eval_id} manual review: ${manualItem.text}`);
    }
  }
  return skippedItems;
}

// ── Confirm helpers ───────────────────────────────────────────────

async function confirmTriggerSummary(
  ctx: ExtensionContext,
  report: EvalReport,
): Promise<boolean> {
  if (report.trigger_results.length === 0) return true;

  const commandFailures = report.output_summary.command_failures ?? 0;
  const warning = commandFailures > 0
    ? `\n\n⚠️ ${commandFailures} command failure(s)/timeout(s). Some eval results may be incomplete.`
    : "";

  const failList = report.trigger_results
    .filter((triggerResult) => !triggerResult.passed)
    .map((triggerResult) => `❌ ${triggerResult.query_id}: ${triggerResult.query}`)
    .join("\n");

  return ctx.ui.confirm(
    "Trigger Evals",
    `${report.trigger_summary.passed}/${report.trigger_summary.total} trigger queries passed.${warning}\n\n${failList || "All passed!"}\n\nContinue to review?`,
  );
}

async function confirmCommandFailures(
  ctx: ExtensionContext,
  report: EvalReport,
): Promise<boolean> {
  const commandFailures = report.output_summary.command_failures ?? 0;
  if (commandFailures <= 0) return true;
  return ctx.ui.confirm(
    "⚠️ Command Failures",
    `${commandFailures} eval command(s) timed out or failed. Some output-eval results may be incomplete. Continue anyway?`,
  );
}

interface ExistingVerdictResolution {
  verdicts: StoredVerdicts;
  cancelled: boolean;
}

async function resolveExistingVerdicts(
  ctx: ExtensionContext,
  runDir: string,
): Promise<ExistingVerdictResolution> {
  const existingVerdicts = loadExistingVerdicts(runDir);
  if (!hasAnyVerdicts(existingVerdicts)) {
    return { verdicts: emptyStoredVerdicts(), cancelled: false };
  }

  const choice = await ctx.ui.select("Existing human review verdicts found", [
    "Resume existing review",
    "Start over",
    "Cancel review",
  ]);

  if (choice === "Resume existing review") {
    return { verdicts: existingVerdicts!, cancelled: false };
  }
  if (choice === "Start over") {
    return { verdicts: emptyStoredVerdicts(), cancelled: false };
  }
  return { verdicts: existingVerdicts!, cancelled: true };
}

function saveVerdicts(runDir: string, verdicts: StoredVerdicts): string {
  const verdictPath = join(runDir, "review-verdicts.json");
  writeFileSync(verdictPath, JSON.stringify(verdicts, null, 2) + "\n", "utf-8");
  return verdictPath;
}

function buildVerdictMarkdown(verdicts: StoredVerdicts, verdictPath: string): string {
  const summary = summarizeVerdicts(verdicts);
  const lines: string[] = [
    "# Interactive Human Review Verdicts",
    "",
    `Saved: ${verdicts.saved_at}`,
    `Machine-readable verdicts: ${verdictPath}`,
    "",
    "## Summary",
    "",
    `- ✅ Passed/accepted: ${summary.passed}`,
    `- ❌ Failed/issues: ${summary.failed}`,
    `- ⏭️ Skipped: ${summary.skipped}`,
  ];

  if (verdicts.trigger_results.length > 0) {
    lines.push("", "## Trigger Verdicts", "");
    for (const triggerVerdict of verdicts.trigger_results) {
      lines.push(
        `- **${triggerVerdict.verdict}** ${triggerVerdict.query_id} (${triggerVerdict.should_trigger ? "should trigger" : "near miss"}, rate ${triggerVerdict.trigger_rate}): ${triggerVerdict.query}`,
      );
      if (triggerVerdict.notes) lines.push(`  - Notes: ${triggerVerdict.notes}`);
    }
  }

  if (verdicts.output_results.length > 0) {
    lines.push("", "## Output Verdicts", "");
    for (const outputVerdict of verdicts.output_results) {
      lines.push(`### ${outputVerdict.eval_id}`, "");
      if (outputVerdict.assertions.length > 0) {
        lines.push("Assertions:");
        for (const item of outputVerdict.assertions) lines.push(`- **${item.verdict}** ${item.text}`);
      }
      if (outputVerdict.manual_review.length > 0) {
        lines.push("", "Manual review:");
        for (const item of outputVerdict.manual_review) lines.push(`- **${item.verdict}** ${item.text}`);
      }
      if (outputVerdict.notes) lines.push("", `Notes: ${outputVerdict.notes}`);
      lines.push("");
    }
  }

  return lines.join("\n").trimEnd() + "\n";
}

function writeVerdictMarkdown(runDir: string, verdicts: StoredVerdicts, verdictPath: string): string {
  const verdictMarkdownPath = join(runDir, "human-review-verdicts.md");
  writeFileSync(verdictMarkdownPath, buildVerdictMarkdown(verdicts, verdictPath), "utf-8");
  return verdictMarkdownPath;
}

function updateLastReview(skillDir: string, verdictMarkdownPath: string): void {
  const lastReviewPath = join(skillDir, "LAST_REVIEW.md");
  if (!existsSync(lastReviewPath)) return;

  const startMarker = "<!-- skill-review-human-verdicts:start -->";
  const endMarker = "<!-- skill-review-human-verdicts:end -->";
  const section = [
    startMarker,
    "",
    "## Interactive Human Review Verdicts",
    "",
    `Human verdicts from the interactive review are saved at: \`${verdictMarkdownPath}\``,
    "",
    endMarker,
  ].join("\n");

  const currentText = readFileSync(lastReviewPath, "utf-8");
  const markerPattern = new RegExp(`${startMarker}[\\s\\S]*?${endMarker}`);
  const nextText = markerPattern.test(currentText)
    ? currentText.replace(markerPattern, section)
    : `${currentText.trimEnd()}\n\n${section}\n`;
  writeFileSync(lastReviewPath, nextText, "utf-8");
}

function buildOutcome(
  runDir: string,
  skillDir: string,
  verdicts: StoredVerdicts,
): InteractiveReviewOutcome {
  const savedVerdicts: StoredVerdicts = {
    ...verdicts,
    saved_at: new Date().toISOString(),
  };
  const verdictPath = saveVerdicts(runDir, savedVerdicts);
  const verdictMarkdownPath = writeVerdictMarkdown(runDir, savedVerdicts, verdictPath);
  updateLastReview(skillDir, verdictMarkdownPath);
  return {
    verdictPath,
    verdictMarkdownPath,
    summary: summarizeVerdicts(savedVerdicts),
    failedItems: collectFailedItems(savedVerdicts),
    skippedItems: collectSkippedItems(savedVerdicts),
    cancelled: false,
  };
}

function cancelledOutcome(runDir: string, verdicts: StoredVerdicts): InteractiveReviewOutcome {
  return {
    verdictPath: join(runDir, "review-verdicts.json"),
    verdictMarkdownPath: join(runDir, "human-review-verdicts.md"),
    summary: summarizeVerdicts(verdicts),
    failedItems: collectFailedItems(verdicts),
    skippedItems: collectSkippedItems(verdicts),
    cancelled: true,
  };
}

async function showReviewSummary(
  ctx: ExtensionContext,
  outcome: InteractiveReviewOutcome,
): Promise<void> {
  await ctx.ui.confirm(
    "Review Complete",
    [
      `✅ ${outcome.summary.passed} passed/accepted`,
      `❌ ${outcome.summary.failed} failed/issues`,
      `⏭️ ${outcome.summary.skipped} skipped`,
      "",
      `Verdicts saved to: ${outcome.verdictPath}`,
      `Markdown summary: ${outcome.verdictMarkdownPath}`,
      `Full review: LAST_REVIEW.md`,
    ].join("\n"),
  );
}

// ── Main review flow ───────────────────────────────────────────────

export async function interactiveReview(
  ctx: ExtensionContext,
  report: EvalReport,
  skillDir: string,
  runDir: string,
): Promise<InteractiveReviewOutcome> {
  const initialResolution = ctx.hasUI
    ? await resolveExistingVerdicts(ctx, runDir)
    : { verdicts: emptyStoredVerdicts(), cancelled: false };
  const verdicts = initialResolution.verdicts;

  if (!ctx.hasUI) {
    return buildOutcome(runDir, skillDir, verdicts);
  }
  if (initialResolution.cancelled) {
    return cancelledOutcome(runDir, verdicts);
  }

  if (!(await confirmTriggerSummary(ctx, report))) {
    return cancelledOutcome(runDir, verdicts);
  }
  if (!(await confirmCommandFailures(ctx, report))) {
    return cancelledOutcome(runDir, verdicts);
  }

  verdicts.trigger_results = await gradeTriggerFailures(
    ctx,
    report,
    verdicts.trigger_results,
    runDir,
    skillDir,
  );
  // Persist after each stage so an interrupted review can be resumed.
  buildOutcome(runDir, skillDir, verdicts);

  const outputVerdictById = new Map(
    verdicts.output_results.map((outputVerdict) => [outputVerdict.eval_id, outputVerdict]),
  );

  for (const evalResult of report.output_results) {
    if (!evalResult.assertions.length && !evalResult.manual_review.length) continue;

    const existingOutputVerdict = outputVerdictById.get(evalResult.eval_id);
    const outputVerdict: OutputVerdict = {
      eval_id: evalResult.eval_id,
      assertions: existingOutputVerdict?.assertions ?? [],
      manual_review: existingOutputVerdict?.manual_review ?? [],
      notes: existingOutputVerdict?.notes,
    };

    const evidenceText = buildOutputEvidenceMarkdown(evalResult);
    const evidencePath = writeEvidenceFile(runDir, evalResult.eval_id, evidenceText);
    ctx.ui.notify(
      `Full review evidence written for ${evalResult.eval_id}: ${evidencePath}`,
      "info",
    );

    outputVerdict.assertions = await gradeGroup(
      ctx,
      ASSERTION_GROUP,
      evalResult.assertions,
      outputVerdict.assertions,
      evalResult.eval_id,
      skillDir,
      evidencePath,
      evidenceText,
    );

    outputVerdict.manual_review = await gradeGroup(
      ctx,
      MANUAL_REVIEW_GROUP,
      evalResult.manual_review,
      outputVerdict.manual_review,
      evalResult.eval_id,
      skillDir,
      evidencePath,
      evidenceText,
    );

    const notes = await ctx.ui.input(
      "Evidence notes (optional — Enter to keep/skip)",
      outputVerdict.notes ? `Existing notes: ${outputVerdict.notes}` : "Any observations about output, behavior, or discrepancies...",
    );
    if (notes?.trim()) outputVerdict.notes = notes.trim();

    outputVerdictById.set(evalResult.eval_id, outputVerdict);
    verdicts.output_results = report.output_results
      .map((currentEvalResult) => outputVerdictById.get(currentEvalResult.eval_id))
      .filter((currentOutputVerdict): currentOutputVerdict is OutputVerdict => Boolean(currentOutputVerdict));
    buildOutcome(runDir, skillDir, verdicts);
  }

  verdicts.output_results = report.output_results
    .map((evalResult) => outputVerdictById.get(evalResult.eval_id))
    .filter((outputVerdict): outputVerdict is OutputVerdict => Boolean(outputVerdict));

  const outcome = buildOutcome(runDir, skillDir, verdicts);
  await showReviewSummary(ctx, outcome);
  return outcome;
}
