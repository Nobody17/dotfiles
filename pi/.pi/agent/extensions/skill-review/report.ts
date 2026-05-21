import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

// ── Report types ───────────────────────────────────────────────────

export interface VariantResult {
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

export interface EvalReport {
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

export function loadReport(runDir: string): EvalReport | null {
  const reportPath = join(runDir, "report.json");
  if (!existsSync(reportPath)) return null;
  try {
    return JSON.parse(readFileSync(reportPath, "utf-8")) as EvalReport;
  } catch {
    return null;
  }
}
