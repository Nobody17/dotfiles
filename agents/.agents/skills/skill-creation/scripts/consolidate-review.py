# /// script
# dependencies = []
# ///

"""Consolidate scattered eval run artifacts into a single, scannable human review file.

Takes the output of `run-skill-evals.py` (a run directory with report.json) and
produces a single `consolidated-review.md` that inlines all key outputs so the
human reviewer does not have to navigate deep directory trees.

Usage:
    python scripts/consolidate-review.py evals/runs/20250101T123000Z/
    python scripts/consolidate-review.py evals/runs/20250101T123000Z/ --output /tmp/review.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

MAX_INLINE_CHARS = 8000
MAX_STDERR_CHARS = 2000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consolidate scattered eval run artifacts into a single, scannable human review file."
    )
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Path to the eval run directory containing report.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write consolidated review to this path (default: <run_dir>/consolidated-review.md)",
    )
    parser.add_argument(
        "--link-to",
        type=Path,
        help="Also create a symlink at this path pointing to the consolidated review",
    )
    return parser.parse_args()


def read_text(path_text: str | None, max_chars: int = MAX_INLINE_CHARS) -> str:
    if not path_text:
        return "(no output captured)"
    path = Path(path_text)
    if not path.exists():
        return "(file not found)"
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n\n... [truncated at {max_chars} chars, full file: {path_text}]"
    return text


def read_json(path_text: str | None) -> dict[str, Any]:
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}


def read_summary(path_text: str | None) -> str:
    """Read a file and return a single-line summary."""
    if not path_text:
        return "(no path)"
    path = Path(path_text)
    if not path.exists():
        return "(not found)"
    content = path.read_text(encoding="utf-8", errors="replace").strip()
    if len(content) > 200:
        return content[:200].replace("\n", " / ") + "..."
    return content.replace("\n", " / ")


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.expanduser().resolve()

    report_path = run_dir / "report.json"
    if not report_path.exists():
        print(f"Error: {report_path} not found. Run `run-skill-evals.py` first.", file=sys.stderr)
        return 1

    report = json.loads(report_path.read_text(encoding="utf-8"))
    output_path = args.output or (run_dir / "consolidated-review.md")

    lines: list[str] = []
    lines.append("# Consolidated Human Review")
    lines.append("")
    lines.append(f"**Skill:** `{report.get('skill_dir', 'unknown')}`")
    lines.append(f"**Run directory:** `{report.get('run_dir', 'unknown')}`")
    lines.append(f"**Created:** `{report.get('created_at', 'unknown')}`")
    lines.append("")
    lines.append("> **How to use this file:** Scan each section. The agent has already run all automated checks.")
    lines.append("> Your job is to verify the outputs that need human judgment. Each section tells you exactly what to look at.")
    lines.append("")

    # ── TRIGGER EVALS ──────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 1. Trigger Evals — Did the skill activate correctly?")
    lines.append("")

    trigger_summary = report.get("trigger_summary", {})
    lines.append(f"**Summary:** {trigger_summary.get('passed', 0)}/{trigger_summary.get('total', 0)} passed")
    lines.append("")

    trigger_results = report.get("trigger_results", [])
    if not trigger_results:
        lines.append("No trigger evals were run.")
    else:
        for result in trigger_results:
            passed_icon = "✅" if result.get("passed") else "❌"
            expected = "SHOULD trigger" if result.get("should_trigger") else "should NOT trigger"
            rate = result.get("trigger_rate", 0.0)
            lines.append(f"### {passed_icon} `{result.get('query_id')}` — {expected} (rate: {rate:.0%})")
            lines.append("")
            lines.append(f"> **Prompt:** {result.get('query', '')}")
            lines.append(f"> **Rate:** {rate:.0%} across {len(result.get('runs', []))} runs")

            if not result.get("passed"):
                lines.append("")
                lines.append("⚠️ **NEEDS HUMAN REVIEW.** See activation evidence below:")
                for run in result.get("runs", []):
                    triggered = "TRIGGERED" if run.get("triggered") else "did NOT trigger"
                    evidence = run.get("activation_evidence", [])
                    lines.append(f"- Run {run.get('run_number')}: {triggered}")
                    if evidence:
                        for ev in evidence:
                            lines.append(f"  - `{ev}`")
            lines.append("")

    # ── OUTPUT EVALS ───────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 2. Output Evals — Did the skill improve results?")
    lines.append("")

    output_summary = report.get("output_summary", {})
    lines.append(
        f"**Summary:** {output_summary.get('completed', 0)} completed, "
        f"{output_summary.get('skipped', 0)} skipped, "
        f"{output_summary.get('command_failures', 0)} command failures"
    )
    lines.append("")

    output_results = report.get("output_results", [])
    if not output_results:
        lines.append("No output evals were run.")
    else:
        for eval_result in output_results:
            eval_id = eval_result.get("eval_id", "unknown")

            if eval_result.get("skipped_reason"):
                lines.append(f"### ⚠️ `{eval_id}` — SKIPPED")
                lines.append(f"**Reason:** {eval_result['skipped_reason']}")
                missing = eval_result.get("missing_files", [])
                if missing:
                    lines.append("**Missing files:**")
                    for mf in missing:
                        lines.append(f"- `{mf}`")
                lines.append("")
                continue

            lines.append(f"### `{eval_id}`")
            lines.append("")
            lines.append(f"**Prompt:** _{eval_result.get('prompt', '')}_")
            expected_output = eval_result.get("expected_output")
            if expected_output:
                lines.append(f"**Expected:** {expected_output}")
            lines.append("")

            # Assertions checklist
            assertions = eval_result.get("assertions", [])
            if assertions:
                lines.append("**Assertions (human must grade):**")
                lines.append("")
                for i, assertion in enumerate(assertions, 1):
                    lines.append(f"- [ ] {i}. {assertion}")
                lines.append("")

            # Judge output if available
            judge_path = eval_result.get("judge_output_path")
            if judge_path:
                lines.append(f"**LLM judge draft:** (see inline below)")
                lines.append("")
                judge_text = read_text(judge_path, max_chars=MAX_INLINE_CHARS)
                lines.append("```text")
                lines.append(judge_text)
                lines.append("```")
                lines.append("")

            # Variant outputs side by side
            for variant in eval_result.get("variants", []):
                variant_name = variant.get("variant", "unknown")
                run_num = variant.get("run_number", 0)
                cmd_result = variant.get("command_result", {})

                lines.append(f"#### {variant_name} (run {run_num})")
                lines.append("")

                # Quick facts
                returncode = cmd_result.get("returncode", "?")
                timed_out = cmd_result.get("timed_out", False)
                activated = variant.get("activated_skill", False)
                changed = variant.get("changed_files", {})

                lines.append(f"- Return code: `{returncode}` | Timeout: `{timed_out}` | Skill activated: `{activated}`")
                if changed:
                    added = changed.get("added", [])
                    modified = changed.get("modified", [])
                    deleted = changed.get("deleted", [])
                    if added:
                        lines.append(f"- Files added: {', '.join(added)}")
                    if modified:
                        lines.append(f"- Files modified: {', '.join(modified)}")
                    if deleted:
                        lines.append(f"- Files deleted: {', '.join(deleted)}")
                lines.append("")

                # Inline stdout
                stdout_path = cmd_result.get("stdout_path")
                lines.append("**stdout:**")
                lines.append("")
                stdout_text = read_text(stdout_path, max_chars=MAX_INLINE_CHARS)
                lines.append("```text")
                lines.append(stdout_text)
                lines.append("```")
                lines.append("")

                # Inline stderr (truncated more aggressively)
                stderr_path = cmd_result.get("stderr_path")
                stderr_text = read_text(stderr_path, max_chars=MAX_STDERR_CHARS)
                if stderr_text and stderr_text != "(no output captured)":
                    lines.append("**stderr:**")
                    lines.append("")
                    lines.append("```text")
                    lines.append(stderr_text)
                    lines.append("```")
                    lines.append("")

            # Manual review items
            manual_review = eval_result.get("manual_review", [])
            if manual_review:
                lines.append("**Additional human review needed:**")
                for item in manual_review:
                    lines.append(f"- [ ] {item}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # ── NEXT STEPS ─────────────────────────────────────────────────
    lines.append("## 3. Next Steps")
    lines.append("")
    lines.append("1. Go through each ❌ or `[ ]` above and mark them PASS/FAIL with evidence")
    lines.append("2. For any FAIL: edit the skill, then rerun the affected eval with:")
    lines.append("   ```bash")
    lines.append(f"   python scripts/run-skill-evals.py {report.get('skill_dir', '.')} --mode output")
    lines.append("   ```")
    lines.append("3. For any trigger FAIL: adjust the skill `description` boundary")
    lines.append("4. Run the static gate again to confirm no regressions:")
    lines.append("   ```bash")
    lines.append(f"   python scripts/test-skill.py {report.get('skill_dir', '.')}")
    lines.append("   ```")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated from `{report_path}`*")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Consolidated review written to: {output_path}")

    # Symlink
    if args.link_to:
        link_path = args.link_to.expanduser().resolve()
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        link_path.symlink_to(output_path)
        print(f"🔗 Symlink created: {link_path} -> {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
