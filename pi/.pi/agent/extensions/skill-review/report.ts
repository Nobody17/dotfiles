import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

// ── Report types ───────────────────────────────────────────────────

export interface CommandResult {
  command?: string[];
  cwd?: string;
  returncode: number | null;
  duration_seconds?: number;
  stdout_path: string;
  stderr_path: string;
  session_paths?: string[];
  timed_out: boolean;
}

export interface TriggerRunResult {
  query_id: string;
  run_number: number;
  should_trigger: boolean;
  triggered: boolean;
  passed: boolean;
  command_result: CommandResult | null;
  activation_evidence: string[];
  run_dir: string;
  skipped_reason?: string | null;
}

export interface VariantResult {
  eval_id?: string;
  variant: string;
  run_number: number;
  command_result: CommandResult | null;
  activated_skill: boolean;
  activation_evidence?: string[];
  changed_files: Record<string, string[]>;
  run_dir: string;
  workspace_dir?: string;
  skipped_reason?: string | null;
}

export interface EvalReport {
  skill_dir: string;
  run_dir: string;
  created_at: string;
  trigger_summary: { total: number; passed: number; failed: number };
  output_summary: {
    total: number;
    completed: number;
    skipped: number;
    command_failures?: number;
  };
  trigger_results: Array<{
    query_id: string;
    query: string;
    should_trigger: boolean;
    trigger_rate: number;
    passed: boolean;
    rationale?: string | null;
    runs: TriggerRunResult[];
  }>;
  output_results: Array<{
    eval_id: string;
    prompt: string;
    expected_output: string | null;
    assertions: string[];
    manual_review: string[];
    missing_files?: string[];
    judge_output_path: string | null;
    variants: VariantResult[];
    skipped_reason?: string | null;
  }>;
  review_path?: string;
}

export type LoadReportResult =
  | { ok: true; report: EvalReport; reportPath: string }
  | { ok: false; error: string; reportPath: string };

function validateReportShape(value: unknown): string | null {
  if (!value || typeof value !== "object") return "report.json is not a JSON object.";
  const report = value as Partial<EvalReport>;
  if (typeof report.skill_dir !== "string") return "report.json is missing string field skill_dir.";
  if (typeof report.run_dir !== "string") return "report.json is missing string field run_dir.";
  if (!Array.isArray(report.trigger_results)) return "report.json is missing array field trigger_results.";
  if (!Array.isArray(report.output_results)) return "report.json is missing array field output_results.";
  return null;
}

export function loadReportWithDiagnostics(runDir: string): LoadReportResult {
  const reportPath = join(runDir, "report.json");
  if (!existsSync(reportPath)) {
    return {
      ok: false,
      reportPath,
      error: `No report.json found at ${reportPath}. Run the eval script first, then consolidate the run.`,
    };
  }

  try {
    const parsedReport = JSON.parse(readFileSync(reportPath, "utf-8")) as unknown;
    const shapeError = validateReportShape(parsedReport);
    if (shapeError) {
      return { ok: false, reportPath, error: shapeError };
    }
    return { ok: true, report: parsedReport as EvalReport, reportPath };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      ok: false,
      reportPath,
      error: `Could not parse ${reportPath}: ${message}`,
    };
  }
}

export function loadReport(runDir: string): EvalReport | null {
  const result = loadReportWithDiagnostics(runDir);
  return result.ok ? result.report : null;
}
