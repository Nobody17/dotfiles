import { isToolCallEventType, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { assessFileDeletion, type DeletionAssessment } from "./assessment.ts";
import { isDirectTemporaryDirectoryDeletion } from "./temporary-directory-policy.ts";

const blockOption = "No, block it";
const allowOption = "Yes, allow deletion";

type ConfirmationOutcome = "approved" | "declined" | "unavailable" | "failed";
type Select = (prompt: string, options: string[]) => Promise<string | undefined>;

function confirmationBlockedReason(outcome: Exclude<ConfirmationOutcome, "approved">): string {
  if (outcome === "declined") return "File deletion declined by user";
  if (outcome === "unavailable") return "File deletion blocked because confirmation is unavailable";
  return "File deletion blocked because confirmation failed";
}

function deletionBlockedResult(outcome: Exclude<ConfirmationOutcome, "approved">) {
  return {
    result: {
      output: `${confirmationBlockedReason(outcome)}.`,
      exitCode: 1,
      cancelled: false,
      truncated: false,
    },
  };
}

function confirmationAssessment(command: string): Exclude<DeletionAssessment, { kind: "safe" }> | undefined {
  const assessment = assessFileDeletion(command);
  if (assessment.kind === "safe") return undefined;
  if (assessment.kind === "deletion" && isDirectTemporaryDirectoryDeletion(command)) return undefined;
  return assessment;
}

function findingsSummary(assessment: Exclude<DeletionAssessment, { kind: "safe" }>): string {
  const messages = [...new Set(assessment.findings.map((finding) => finding.message))].slice(0, 6);
  if (messages.length === 0) return "The command could not be assessed safely.";
  return messages.map((message) => `• ${message}`).join("\n");
}

async function confirmFileDeletion(
  command: string,
  assessment: Exclude<DeletionAssessment, { kind: "safe" }>,
  select: Select,
): Promise<ConfirmationOutcome> {
  try {
    const choice = await select(
      `File deletion may occur:\n\n${command}\n\nFindings:\n${findingsSummary(assessment)}\n\nAllow it to run?`,
      [blockOption, allowOption],
    );
    return choice === allowOption ? "approved" : "declined";
  } catch {
    return "failed";
  }
}

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    if (!isToolCallEventType("bash", event)) return undefined;

    const assessment = confirmationAssessment(event.input.command);
    if (assessment === undefined) return undefined;

    if (ctx.mode !== "tui" || !ctx.hasUI) {
      return { block: true, reason: confirmationBlockedReason("unavailable") };
    }

    const outcome = await confirmFileDeletion(event.input.command, assessment, ctx.ui.select.bind(ctx.ui));
    return outcome === "approved"
      ? undefined
      : { block: true, reason: confirmationBlockedReason(outcome) };
  });

  pi.on("user_bash", async (event, ctx) => {
    const assessment = confirmationAssessment(event.command);
    if (assessment === undefined) return undefined;

    if (ctx.mode !== "tui" || !ctx.hasUI) {
      return deletionBlockedResult("unavailable");
    }

    const outcome = await confirmFileDeletion(event.command, assessment, ctx.ui.select.bind(ctx.ui));
    return outcome === "approved" ? undefined : deletionBlockedResult(outcome);
  });
}
