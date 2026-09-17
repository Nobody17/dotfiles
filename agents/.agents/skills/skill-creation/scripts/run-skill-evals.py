#!/usr/bin/env python3
"""Run trigger and output evals for an Agent Skill using the pi CLI.

The script automates everything that can be observed from pi session logs and
writes a review guide for the remaining human judgment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_TRIGGER_RUNS = 3
DEFAULT_OUTPUT_RUNS = 1
DEFAULT_TIMEOUT_SECONDS = 6000
MAX_REVIEW_SNIPPET_CHARS = 6000


@dataclass
class CommandResult:
    command: list[str]
    cwd: str
    returncode: int | None
    duration_seconds: float
    stdout_path: str
    stderr_path: str
    session_paths: list[str]
    timed_out: bool = False


@dataclass
class FixtureSpec:
    source: str
    target: str


@dataclass
class TriggerRunResult:
    query_id: str
    run_number: int
    should_trigger: bool
    triggered: bool
    passed: bool
    command_result: CommandResult | None
    activation_evidence: list[str]
    run_dir: str
    skipped_reason: str | None = None


@dataclass
class TriggerEvalResult:
    query_id: str
    query: str
    should_trigger: bool
    trigger_rate: float
    passed: bool
    runs: list[TriggerRunResult]
    rationale: str | None = None


@dataclass
class OutputVariantResult:
    eval_id: str
    variant: str
    run_number: int
    command_result: CommandResult | None
    activated_skill: bool
    activation_evidence: list[str]
    changed_files: dict[str, list[str]]
    run_dir: str
    workspace_dir: str
    skipped_reason: str | None = None


@dataclass
class OutputEvalResult:
    eval_id: str
    prompt: str
    expected_output: str | None
    assertions: list[str]
    manual_review: list[str]
    missing_files: list[str]
    variants: list[OutputVariantResult]
    judge_output_path: str | None = None
    skipped_reason: str | None = None


@dataclass
class EvalReport:
    skill_dir: str
    run_dir: str
    created_at: str
    trigger_summary: dict[str, int]
    output_summary: dict[str, int]
    trigger_results: list[TriggerEvalResult]
    output_results: list[OutputEvalResult]
    review_path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Agent Skill trigger/output evals through pi, capture session logs, "
            "and write a review guide for remaining human judgment."
        )
    )
    parser.add_argument(
        "skill_dir",
        type=Path,
        help="Path to the skill directory containing SKILL.md and evals/",
    )
    parser.add_argument(
        "--mode",
        choices=("all", "trigger", "output"),
        default="all",
        help="Eval type to run",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="Directory for eval artifacts (default: <skill>/evals/runs/<timestamp>)",
    )
    parser.add_argument(
        "--fixture-root",
        type=Path,
        help="Root used to resolve output eval files (default: skill directory)",
    )
    parser.add_argument(
        "--pi-bin", default="pi", help="pi executable to invoke (default: pi)"
    )
    parser.add_argument("--provider", help="Optional pi provider to pass through")
    parser.add_argument("--model", help="Optional pi model to pass through")
    parser.add_argument(
        "--trigger-runs",
        type=int,
        default=DEFAULT_TRIGGER_RUNS,
        help="Runs per trigger query",
    )
    parser.add_argument(
        "--output-runs",
        type=int,
        default=DEFAULT_OUTPUT_RUNS,
        help="Runs per output eval variant",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Timeout per pi invocation in seconds",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write commands/review plan without invoking pi",
    )
    parser.add_argument(
        "--allow-missing-files",
        action="store_true",
        help="Run output evals even when listed fixture files are missing",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Skip baseline/no-skill output eval runs",
    )
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Ask pi to draft assertion grading for output evals after runs complete",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when trigger evals fail or commands fail",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="Resume a previous eval run from the given directory (skips already-completed runs)",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SystemExit(f"Missing eval file: {path}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {path}: {error}") from error


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-").lower()
    return slug or "unnamed"


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def resolve_skill_dir(skill_dir: Path) -> Path:
    resolved = skill_dir.expanduser().resolve()
    if not resolved.is_dir():
        raise SystemExit(f"Skill path is not a directory: {resolved}")
    if not (resolved / "SKILL.md").exists():
        raise SystemExit(f"Skill directory is missing SKILL.md: {resolved}")
    return resolved


def resolve_pi_bin(pi_bin: str) -> str | None:
    if os.sep in pi_bin or (os.altsep and os.altsep in pi_bin):
        return (
            str(Path(pi_bin).expanduser().resolve()) if Path(pi_bin).exists() else None
        )
    return shutil.which(pi_bin)


def common_pi_args(args: argparse.Namespace, session_dir: Path) -> list[str]:
    command = [
        args.pi_executable,
        "--session-dir",
        str(session_dir),
        "--no-context-files",
        "--print",
        "--mode",
        "text",
    ]
    if args.provider:
        command.extend(["--provider", args.provider])
    if args.model:
        command.extend(["--model", args.model])
    return command


def run_subprocess(
    command: list[str], cwd: Path, timeout: int, run_dir: Path
) -> CommandResult:
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    command_path = run_dir / "command.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        command_path, {"command": command, "cwd": str(cwd), "timeout_seconds": timeout}
    )

    started_at = time.monotonic()
    timed_out = False
    returncode: int | None
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        stderr += f"\nTimed out after {timeout} seconds.\n"
        returncode = None
        timed_out = True

    duration_seconds = time.monotonic() - started_at
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    session_paths = [
        str(path) for path in sorted((run_dir / "sessions").rglob("*.jsonl"))
    ]
    result = CommandResult(
        command=command,
        cwd=str(cwd),
        returncode=returncode,
        duration_seconds=duration_seconds,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        session_paths=session_paths,
        timed_out=timed_out,
    )
    write_json(run_dir / "result.json", asdict(result))
    return result


def write_dry_run(command: list[str], cwd: Path, run_dir: Path) -> CommandResult:
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    stdout_path.write_text("DRY RUN: command was not executed.\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    result = CommandResult(
        command=command,
        cwd=str(cwd),
        returncode=0,
        duration_seconds=0.0,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        session_paths=[],
    )
    write_json(
        run_dir / "command.json", {"command": command, "cwd": str(cwd), "dry_run": True}
    )
    write_json(run_dir / "result.json", asdict(result))
    return result


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def iter_tool_calls(session_path: Path) -> list[dict[str, Any]]:
    tool_calls: list[dict[str, Any]] = []
    for record in read_jsonl(session_path):
        if record.get("type") != "message":
            continue
        message = record.get("message", {})
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == "toolCall":
                tool_calls.append(item)
    return tool_calls


def stringify_arguments(arguments: Any) -> str:
    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments, sort_keys=True, ensure_ascii=False)


def extract_path_argument(arguments: Any) -> str | None:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return None
    if not isinstance(arguments, dict):
        return None
    for key in ("path", "file", "file_path", "filename"):
        value = arguments.get(key)
        if isinstance(value, str):
            return value
    return None


def matches_skill_path(raw_path: str, invocation_cwd: Path, skill_md: Path) -> bool:
    expanded = Path(raw_path).expanduser()
    candidates = []
    if expanded.is_absolute():
        candidates.append(expanded)
    else:
        candidates.append(invocation_cwd / expanded)
    for candidate in candidates:
        try:
            if candidate.resolve() == skill_md.resolve():
                return True
        except OSError:
            continue

    normalized_raw = raw_path.replace("\\", "/")
    normalized_skill = str(skill_md).replace("\\", "/")
    return normalized_skill in normalized_raw


def detect_skill_activation(
    session_paths: list[str], invocation_cwd: Path, skill_dir: Path
) -> tuple[bool, list[str]]:
    skill_md = skill_dir / "SKILL.md"
    evidence: list[str] = []

    for session_path_text in session_paths:
        session_path = Path(session_path_text)
        for tool_call in iter_tool_calls(session_path):
            tool_name = str(tool_call.get("name", ""))
            arguments = tool_call.get("arguments", {})
            path_argument = extract_path_argument(arguments)
            arguments_text = stringify_arguments(arguments)

            if path_argument and matches_skill_path(
                path_argument, invocation_cwd, skill_md
            ):
                evidence.append(
                    f"{session_path}: tool `{tool_name}` read `{path_argument}`"
                )
                continue

            normalized_skill = str(skill_md).replace("\\", "/")
            if normalized_skill in arguments_text.replace("\\", "/"):
                evidence.append(
                    f"{session_path}: tool `{tool_name}` referenced `{skill_md}`"
                )

    return bool(evidence), evidence


def file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_command_result(run_dir: Path) -> CommandResult | None:
    """Load a previously saved CommandResult from result.json, or None if missing."""
    result_path = run_dir / "result.json"
    if not result_path.exists():
        return None
    try:
        data = load_json(result_path)
        return CommandResult(
            command=data.get("command", []),
            cwd=data.get("cwd", ""),
            returncode=data.get("returncode"),
            duration_seconds=data.get("duration_seconds", 0.0),
            stdout_path=data.get("stdout_path", ""),
            stderr_path=data.get("stderr_path", ""),
            session_paths=data.get("session_paths", []),
            timed_out=data.get("timed_out", False),
        )
    except (KeyError, TypeError):
        return None


def snapshot_files(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    if not root.exists():
        return snapshot
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snapshot[str(path.relative_to(root))] = file_hash(path)
    return snapshot


def diff_snapshots(
    before: dict[str, str], after: dict[str, str]
) -> dict[str, list[str]]:
    before_keys = set(before)
    after_keys = set(after)
    return {
        "added": sorted(after_keys - before_keys),
        "modified": sorted(
            key for key in before_keys & after_keys if before[key] != after[key]
        ),
        "deleted": sorted(before_keys - after_keys),
    }


def parse_fixture_specs(raw_files: list[Any]) -> list[FixtureSpec]:
    specs: list[FixtureSpec] = []
    for item in raw_files:
        if isinstance(item, str):
            specs.append(FixtureSpec(source=item, target=item))
            continue
        if isinstance(item, dict):
            source = item.get("source")
            target = item.get("target", source)
            if isinstance(source, str) and isinstance(target, str):
                specs.append(FixtureSpec(source=source, target=target))
                continue
        raise SystemExit(
            f"Invalid output eval file entry: {item!r}. Use a string or {{'source': ..., 'target': ...}}."
        )
    return specs


def copy_fixture_files(
    file_specs: list[FixtureSpec], fixture_root: Path, workspace: Path
) -> tuple[list[str], list[str]]:
    copied: list[str] = []
    missing: list[str] = []
    for file_spec in file_specs:
        source = Path(file_spec.source).expanduser()
        relative_destination = Path(file_spec.target)
        if source.is_absolute():
            if not source.exists():
                missing.append(f"{file_spec.source} -> {file_spec.target}")
                continue
        else:
            source = fixture_root / source

        if relative_destination.is_absolute():
            raise SystemExit(
                f"Output eval fixture target must be relative: {file_spec.target}"
            )

        if not source.exists() or not source.is_file():
            missing.append(f"{file_spec.source} -> {file_spec.target}")
            continue

        destination = workspace / relative_destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(str(relative_destination))
    return copied, missing


def build_trigger_command(
    args: argparse.Namespace, skill_dir: Path, session_dir: Path, query: str
) -> list[str]:
    command = common_pi_args(args, session_dir)
    command.extend(["--no-skills", "--skill", str(skill_dir), "--tools", "read", query])
    return command


def build_output_command(
    args: argparse.Namespace,
    skill_dir: Path,
    session_dir: Path,
    prompt: str,
    copied_files: list[str],
    with_skill: bool,
) -> list[str]:
    command = common_pi_args(args, session_dir)
    command.extend(
        [
            "--no-skills",
            "--append-system-prompt",
            (
                "Evaluation sandbox: work only inside the current working directory. "
                "Do not access or modify files outside it unless the user explicitly asks. "
                "At the end, summarize changed files and validation performed."
            ),
        ]
    )
    if with_skill:
        command.extend(["--skill", str(skill_dir)])
    command.extend(f"@{file_path}" for file_path in copied_files)
    command.append(prompt)
    return command


def run_trigger_evals(
    args: argparse.Namespace, skill_dir: Path, run_dir: Path
) -> list[TriggerEvalResult]:
    trigger_path = skill_dir / "evals" / "trigger-queries.json"
    data = load_json(trigger_path)
    results: list[TriggerEvalResult] = []

    for query_data in data.get("queries", []):
        query_id = str(query_data.get("id", "unnamed"))
        query = str(query_data.get("query", ""))
        should_trigger = bool(query_data.get("should_trigger", False))
        rationale = query_data.get("rationale")
        run_results: list[TriggerRunResult] = []

        for run_number in range(1, args.trigger_runs + 1):
            eval_run_dir = run_dir / "trigger" / slugify(query_id) / f"run-{run_number}"

            # Resume: skip if result already exists
            if args.resume:
                existing = load_command_result(eval_run_dir)
                if existing is not None:
                    triggered, evidence = detect_skill_activation(
                        existing.session_paths, eval_run_dir / "workspace", skill_dir
                    )
                    passed = triggered if should_trigger else not triggered
                    run_results.append(
                        TriggerRunResult(
                            query_id=query_id,
                            run_number=run_number,
                            should_trigger=should_trigger,
                            triggered=triggered,
                            passed=passed,
                            command_result=existing,
                            activation_evidence=evidence,
                            run_dir=str(eval_run_dir),
                        )
                    )
                    continue

            workspace = eval_run_dir / "workspace"
            session_dir = eval_run_dir / "sessions"
            workspace.mkdir(parents=True, exist_ok=True)
            session_dir.mkdir(parents=True, exist_ok=True)
            command = build_trigger_command(args, skill_dir, session_dir, query)

            if args.dry_run:
                command_result = write_dry_run(command, workspace, eval_run_dir)
                triggered = should_trigger
                evidence = [
                    "dry run; pi was not invoked and activation was not measured"
                ]
                passed = True
            else:
                command_result = run_subprocess(
                    command, workspace, args.timeout, eval_run_dir
                )
                triggered, evidence = detect_skill_activation(
                    command_result.session_paths, workspace, skill_dir
                )
                passed = triggered if should_trigger else not triggered
            run_results.append(
                TriggerRunResult(
                    query_id=query_id,
                    run_number=run_number,
                    should_trigger=should_trigger,
                    triggered=triggered,
                    passed=passed,
                    command_result=command_result,
                    activation_evidence=evidence,
                    run_dir=str(eval_run_dir),
                    skipped_reason="dry run" if args.dry_run else None,
                )
            )

        trigger_count = sum(1 for run_result in run_results if run_result.triggered)
        trigger_rate = trigger_count / len(run_results) if run_results else 0.0
        passed = trigger_rate > 0.5 if should_trigger else trigger_rate < 0.5
        results.append(
            TriggerEvalResult(
                query_id=query_id,
                query=query,
                should_trigger=should_trigger,
                trigger_rate=trigger_rate,
                passed=passed,
                runs=run_results,
                rationale=str(rationale) if rationale is not None else None,
            )
        )

    return results


def run_output_variant(
    args: argparse.Namespace,
    skill_dir: Path,
    eval_id: str,
    prompt: str,
    copied_files: list[str],
    output_root: Path,
    variant: str,
    run_number: int,
) -> OutputVariantResult:
    run_dir = output_root / slugify(eval_id) / variant / f"run-{run_number}"

    # Resume: skip if result already exists
    if args.resume:
        existing = load_command_result(run_dir)
        if existing is not None:
            changed_path = run_dir / "changed-files.json"
            changed_files = (
                load_json(changed_path)
                if changed_path.exists()
                else {"added": [], "modified": [], "deleted": []}
            )
            activated_skill, evidence = detect_skill_activation(
                existing.session_paths, run_dir / "workspace", skill_dir
            )
            return OutputVariantResult(
                eval_id=eval_id,
                variant=variant,
                run_number=run_number,
                command_result=existing,
                activated_skill=activated_skill,
                activation_evidence=evidence,
                changed_files=changed_files,
                run_dir=str(run_dir),
                workspace_dir=str(run_dir / "workspace"),
            )

    workspace = run_dir / "workspace"
    session_dir = run_dir / "sessions"
    workspace.mkdir(parents=True, exist_ok=True)
    session_dir.mkdir(parents=True, exist_ok=True)

    for relative_file in copied_files:
        source = output_root / slugify(eval_id) / "fixtures" / relative_file
        destination = workspace / relative_file
        if source.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    before = snapshot_files(workspace)
    command = build_output_command(
        args,
        skill_dir,
        session_dir,
        prompt,
        copied_files,
        with_skill=variant == "with_skill",
    )

    if args.dry_run:
        command_result = write_dry_run(command, workspace, run_dir)
    else:
        command_result = run_subprocess(command, workspace, args.timeout, run_dir)

    after = snapshot_files(workspace)
    changed_files = diff_snapshots(before, after)
    write_json(run_dir / "changed-files.json", changed_files)
    activated_skill, evidence = detect_skill_activation(
        command_result.session_paths, workspace, skill_dir
    )

    return OutputVariantResult(
        eval_id=eval_id,
        variant=variant,
        run_number=run_number,
        command_result=command_result,
        activated_skill=activated_skill,
        activation_evidence=evidence,
        changed_files=changed_files,
        run_dir=str(run_dir),
        workspace_dir=str(workspace),
        skipped_reason="dry run" if args.dry_run else None,
    )


def run_output_evals(
    args: argparse.Namespace, skill_dir: Path, run_dir: Path
) -> list[OutputEvalResult]:
    output_path = skill_dir / "evals" / "output-evals.json"
    data = load_json(output_path)
    results: list[OutputEvalResult] = []
    output_root = run_dir / "output"

    for eval_data in data.get("evals", []):
        eval_id = str(eval_data.get("id", "unnamed"))
        prompt = str(eval_data.get("prompt", ""))
        expected_output = eval_data.get("expected_output")
        assertions = [str(assertion) for assertion in eval_data.get("assertions", [])]
        manual_review = [str(item) for item in eval_data.get("manual_review", [])]
        file_specs = parse_fixture_specs(eval_data.get("files", []))
        fixture_dir = output_root / slugify(eval_id) / "fixtures"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        copied_files, missing_files = copy_fixture_files(
            file_specs, args.fixture_root.resolve(), fixture_dir
        )

        if missing_files and not args.allow_missing_files:
            results.append(
                OutputEvalResult(
                    eval_id=eval_id,
                    prompt=prompt,
                    expected_output=str(expected_output)
                    if expected_output is not None
                    else None,
                    assertions=assertions,
                    manual_review=manual_review,
                    missing_files=missing_files,
                    variants=[],
                    skipped_reason="missing fixture files",
                )
            )
            continue

        variants: list[OutputVariantResult] = []
        variant_names = (
            ["with_skill"] if args.no_baseline else ["with_skill", "baseline"]
        )
        for variant in variant_names:
            for run_number in range(1, args.output_runs + 1):
                variants.append(
                    run_output_variant(
                        args=args,
                        skill_dir=skill_dir,
                        eval_id=eval_id,
                        prompt=prompt,
                        copied_files=copied_files,
                        output_root=output_root,
                        variant=variant,
                        run_number=run_number,
                    )
                )

        output_result = OutputEvalResult(
            eval_id=eval_id,
            prompt=prompt,
            expected_output=str(expected_output)
            if expected_output is not None
            else None,
            assertions=assertions,
            manual_review=manual_review,
            missing_files=missing_files,
            variants=variants,
        )
        if args.llm_judge and not args.dry_run:
            output_result.judge_output_path = run_llm_judge(
                args, output_result, output_root / slugify(eval_id) / "judge"
            )
        results.append(output_result)

    return results


def read_text_if_exists(
    path_text: str | None, max_chars: int = MAX_REVIEW_SNIPPET_CHARS
) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]"
    return text


def run_llm_judge(
    args: argparse.Namespace, output_result: OutputEvalResult, judge_dir: Path
) -> str:
    judge_dir.mkdir(parents=True, exist_ok=True)
    session_dir = judge_dir / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    judge_input = judge_dir / "judge-input.md"

    variant_sections: list[str] = []
    for variant in output_result.variants:
        command_result = variant.command_result
        stdout_text = read_text_if_exists(
            command_result.stdout_path if command_result else None
        )
        stderr_text = read_text_if_exists(
            command_result.stderr_path if command_result else None, max_chars=2000
        )
        variant_sections.append(
            f"## {variant.variant} run {variant.run_number}\n"
            f"- Run dir: `{variant.run_dir}`\n"
            f"- Workspace: `{variant.workspace_dir}`\n"
            f"- Activated skill: `{variant.activated_skill}`\n"
            f"- Changed files: `{json.dumps(variant.changed_files)}`\n\n"
            f"### stdout\n```text\n{stdout_text}\n```\n\n"
            f"### stderr\n```text\n{stderr_text}\n```\n"
        )

    judge_input.write_text(
        "# Skill Output Eval Judge Input\n\n"
        "Draft PASS/FAIL grading for the assertions below. Use concrete evidence. "
        "If evidence is not available from the captured outputs, mark the assertion as NEEDS_HUMAN_REVIEW. "
        "Return concise Markdown; do not modify files.\n\n"
        f"## Eval `{output_result.eval_id}`\n\n"
        f"Prompt:\n```text\n{output_result.prompt}\n```\n\n"
        f"Expected output:\n```text\n{output_result.expected_output or ''}\n```\n\n"
        "Assertions:\n"
        + "\n".join(f"- {assertion}" for assertion in output_result.assertions)
        + "\n\nManual review points:\n"
        + "\n".join(f"- {item}" for item in output_result.manual_review)
        + "\n\n"
        + "\n\n".join(variant_sections),
        encoding="utf-8",
    )

    command = common_pi_args(args, session_dir)
    command.extend(
        [
            "--no-skills",
            "--no-tools",
            f"@{judge_input.name}",
            "Grade this skill eval from the attached judge input.",
        ]
    )
    result = run_subprocess(command, judge_dir, args.timeout, judge_dir)
    return result.stdout_path


def trigger_summary(results: list[TriggerEvalResult]) -> dict[str, int]:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    return {"total": total, "passed": passed, "failed": total - passed}


def output_summary(results: list[OutputEvalResult]) -> dict[str, int]:
    total = len(results)
    skipped = sum(1 for result in results if result.skipped_reason)
    completed = total - skipped
    command_failures = 0
    for result in results:
        for variant in result.variants:
            command_result = variant.command_result
            if command_result and command_result.returncode not in (0, None):
                command_failures += 1
            if command_result and command_result.timed_out:
                command_failures += 1
    return {
        "total": total,
        "completed": completed,
        "skipped": skipped,
        "command_failures": command_failures,
    }


def markdown_link(path_text: str | None, label: str | None = None) -> str:
    if not path_text:
        return ""
    label = label or path_text
    return f"[{label}]({path_text})"


def write_review(report: EvalReport) -> None:
    review_path = Path(report.review_path)
    dry_run = any(
        run.skipped_reason == "dry run"
        for result in report.trigger_results
        for run in result.runs
    ) or any(
        variant.skipped_reason == "dry run"
        for result in report.output_results
        for variant in result.variants
    )
    lines: list[str] = []
    lines.append("# Skill Eval Review")
    lines.append("")
    lines.append(f"- Skill: `{report.skill_dir}`")
    lines.append(f"- Run dir: `{report.run_dir}`")
    lines.append(f"- Created: `{report.created_at}`")
    lines.append(
        f"- Full machine-readable report: `{Path(report.run_dir) / 'report.json'}`"
    )
    if dry_run:
        lines.append(
            "- Mode: **dry run** — commands were written but not executed; activation/pass values are placeholders."
        )
    lines.append("")

    lines.append("## Trigger evals")
    lines.append("")
    lines.append(
        f"Automated summary: {report.trigger_summary.get('passed', 0)}/"
        f"{report.trigger_summary.get('total', 0)} query groups passed."
    )
    lines.append("")
    if report.trigger_results:
        lines.append("| Query | Expected | Trigger rate | Result | Where to inspect |")
        lines.append("|---|---:|---:|---|---|")
        for result in report.trigger_results:
            expected = "trigger" if result.should_trigger else "not trigger"
            status = "PASS" if result.passed else "FAIL"
            first_run_dir = result.runs[0].run_dir if result.runs else ""
            lines.append(
                f"| `{result.query_id}` | {expected} | {result.trigger_rate:.2f} | {status} | `{first_run_dir}` |"
            )
    else:
        lines.append("No trigger evals were run.")
    lines.append("")
    lines.append(
        "Human review is usually only needed for failed or surprising trigger results:"
    )
    lines.append("- Open the run directory in the table.")
    lines.append(
        "- Read `stdout.txt` for the final answer and `stderr.txt` for pi errors."
    )
    lines.append(
        "- Inspect `sessions/**/*.jsonl` and confirm whether a `read` tool call loaded the target `SKILL.md`."
    )
    lines.append(
        "- If a should-trigger prompt did not load the skill, broaden the skill description. If a near miss loaded it, narrow the description boundary."
    )
    lines.append("")

    lines.append("## Output evals")
    lines.append("")
    lines.append(
        f"Automated run summary: {report.output_summary.get('completed', 0)} completed, "
        f"{report.output_summary.get('skipped', 0)} skipped, "
        f"{report.output_summary.get('command_failures', 0)} command failures/timeouts."
    )
    lines.append("")
    if not report.output_results:
        lines.append("No output evals were run.")
    for result in report.output_results:
        lines.append(f"### `{result.eval_id}`")
        lines.append("")
        if result.skipped_reason:
            lines.append(f"Skipped: **{result.skipped_reason}**")
            if result.missing_files:
                lines.append("")
                lines.append(
                    "Missing fixture files to create or correct before rerunning:"
                )
                lines.extend(
                    f"- `{missing_file}`" for missing_file in result.missing_files
                )
            lines.append("")
            continue

        if result.expected_output:
            lines.append(f"Expected output: {result.expected_output}")
            lines.append("")

        lines.append("Run artifacts:")
        for variant in result.variants:
            command_result = variant.command_result
            lines.append(f"- **{variant.variant} run {variant.run_number}**")
            lines.append(f"  - Run dir: `{variant.run_dir}`")
            lines.append(f"  - Workspace after run: `{variant.workspace_dir}`")
            if command_result:
                lines.append(f"  - stdout: `{command_result.stdout_path}`")
                lines.append(f"  - stderr: `{command_result.stderr_path}`")
                lines.append(f"  - sessions: `{Path(variant.run_dir) / 'sessions'}`")
                lines.append(
                    f"  - return code: `{command_result.returncode}` timeout: `{command_result.timed_out}`"
                )
            activation_text = (
                "not measured (dry run)"
                if variant.skipped_reason == "dry run"
                else str(variant.activated_skill)
            )
            lines.append(f"  - activated target skill: `{activation_text}`")
            lines.append(
                f"  - changed files summary: `{Path(variant.run_dir) / 'changed-files.json'}`"
            )
        lines.append("")

        if result.judge_output_path:
            lines.append(f"LLM judge draft: `{result.judge_output_path}`")
            lines.append(
                "Use this as a starting point; verify concrete evidence before accepting PASS grades."
            )
            lines.append("")

        lines.append("Human review required:")
        lines.append(
            "1. Compare `with_skill/*/stdout.txt` against `baseline/*/stdout.txt` when a baseline exists."
        )
        lines.append(
            "2. Inspect each `workspace/` and `changed-files.json` to see what the agent actually changed."
        )
        lines.append("3. Grade these assertions with PASS/FAIL plus evidence:")
        if result.assertions:
            lines.extend(f"   - {assertion}" for assertion in result.assertions)
        else:
            lines.append(
                "   - No assertions were listed; add assertions to `evals/output-evals.json`."
            )
        if result.manual_review:
            lines.append("4. Also review:")
            lines.extend(f"   - {item}" for item in result.manual_review)
        lines.append("")

    review_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(
    skill_dir: Path,
    run_dir: Path,
    trigger_results: list[TriggerEvalResult],
    output_results: list[OutputEvalResult],
) -> EvalReport:
    review_path = run_dir / "review.md"
    return EvalReport(
        skill_dir=str(skill_dir),
        run_dir=str(run_dir),
        created_at=datetime.now(UTC).isoformat(),
        trigger_summary=trigger_summary(trigger_results),
        output_summary=output_summary(output_results),
        trigger_results=trigger_results,
        output_results=output_results,
        review_path=str(review_path),
    )


def has_strict_failure(report: EvalReport) -> bool:
    if report.trigger_summary.get("failed", 0) > 0:
        return True
    if report.output_summary.get("command_failures", 0) > 0:
        return True
    return False


def main() -> int:
    args = parse_args()
    skill_dir = resolve_skill_dir(args.skill_dir)
    args.fixture_root = (
        args.fixture_root.expanduser().resolve() if args.fixture_root else skill_dir
    )
    args.pi_executable = resolve_pi_bin(args.pi_bin)

    if not args.pi_executable and not args.dry_run:
        raise SystemExit(
            f"Could not find pi executable: {args.pi_bin}. Use --pi-bin or --dry-run."
        )
    if not args.pi_executable:
        args.pi_executable = args.pi_bin

    run_dir = args.run_dir or (skill_dir / "evals" / "runs" / utc_timestamp())
    if args.resume is not None:
        run_dir = args.resume.expanduser().resolve()
        if not run_dir.exists():
            raise SystemExit(f"Resume run directory not found: {run_dir}")
    run_dir = run_dir.expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.resume is not None:
        print(f"Resuming eval run in: {run_dir}")

    trigger_results: list[TriggerEvalResult] = []
    output_results: list[OutputEvalResult] = []

    if args.mode in ("all", "trigger"):
        trigger_results = run_trigger_evals(args, skill_dir, run_dir)
    if args.mode in ("all", "output"):
        output_results = run_output_evals(args, skill_dir, run_dir)

    report = build_report(skill_dir, run_dir, trigger_results, output_results)
    write_json(run_dir / "report.json", asdict(report))
    write_review(report)

    print(f"Wrote eval report: {run_dir / 'report.json'}")
    print(f"Wrote human review guide: {report.review_path}")
    print(f"Trigger: {report.trigger_summary}")
    print(f"Output: {report.output_summary}")

    if args.strict and has_strict_failure(report):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
