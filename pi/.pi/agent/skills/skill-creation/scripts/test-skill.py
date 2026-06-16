#!/usr/bin/env python3
"""Universal static test runner and manual eval planner for Agent Skills."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is optional; fallback parser handles common checks.
    yaml = None

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_SKILL_LINES = 500
LONG_REFERENCE_LINES = 100

LOCAL_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
WINDOWS_PATH_PATTERN = re.compile(r"(?:scripts|references|assets)\\\\")

ANTI_PATTERN_HINTS = {
    "helps with": "Description may be vague; say what the skill does and when to use it.",
    "handle errors appropriately": "Generic instruction; replace with concrete error handling or validation steps.",
    "follow best practices": "Generic instruction; name the specific practices that matter here.",
    "make sure to": "Often vague; consider a concrete command, check, or assertion.",
}

PLACEHOLDER_TEXT = (
    "replace-with-skill-name",
    "Realistic user prompt",
    "Realistic adjacent prompt",
    "Why this skill should be used",
    "Why this is outside the skill boundary",
    "Realistic task the skill should handle",
    "Human-readable description of success",
    "Observable, verifiable assertion",
)

GENERATED_ARTIFACT_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store"}
GENERATED_ARTIFACT_SUFFIXES = {".pyc", ".pyo"}

TRIGGER_TEMPLATE = {
    "skill_name": "replace-with-skill-name",
    "queries": [
        {
            "id": "should-trigger-1",
            "query": "Realistic user prompt that should activate this skill.",
            "should_trigger": True,
            "rationale": "Why this skill should be used.",
        },
        {
            "id": "near-miss-1",
            "query": "Realistic adjacent prompt that should not activate this skill.",
            "should_trigger": False,
            "rationale": "Why this is outside the skill boundary.",
        },
    ],
}

OUTPUT_TEMPLATE = {
    "skill_name": "replace-with-skill-name",
    "evals": [
        {
            "id": "core-workflow-1",
            "prompt": "Realistic task the skill should handle.",
            "files": [],
            "expected_output": "Human-readable description of success.",
            "assertions": [
                "Observable, verifiable assertion about the output.",
                "Another assertion, preferably checkable from produced files or text.",
            ],
            "manual_review": [
                "Inspect whether the agent followed the skill workflow rather than generic reasoning.",
                "Inspect whether it loaded only relevant reference files.",
            ],
        }
    ],
}


@dataclass
class Finding:
    level: str
    check: str
    message: str
    path: str | None = None
    manual_next_step: str | None = None


@dataclass
class Report:
    skill_path: str
    passed: bool
    findings: list[Finding]
    manual_workflow: list[str]


def parse_frontmatter(skill_md: Path) -> tuple[dict[str, Any], str, list[Finding]]:
    text = skill_md.read_text(encoding="utf-8")
    findings: list[Finding] = []
    if not text.startswith("---\n"):
        findings.append(Finding("error", "frontmatter", "SKILL.md must start with YAML frontmatter.", str(skill_md)))
        return {}, text, findings

    parts = text.split("---", 2)
    if len(parts) < 3:
        findings.append(Finding("error", "frontmatter", "YAML frontmatter is not closed with ---.", str(skill_md)))
        return {}, text, findings

    frontmatter = parts[1]
    if yaml is not None:
        try:
            parsed = yaml.safe_load(frontmatter) or {}
        except Exception as error:
            findings.append(
                Finding(
                    "error",
                    "frontmatter",
                    f"Invalid YAML frontmatter: {error}",
                    str(skill_md),
                    "Quote frontmatter values containing ': ' (for example, use description: \"...\") or use a folded block scalar.",
                )
            )
            return {}, parts[2], findings
        if not isinstance(parsed, dict):
            findings.append(Finding("error", "frontmatter", "YAML frontmatter must be a mapping.", str(skill_md)))
            return {}, parts[2], findings
        return parsed, parts[2], findings

    metadata: dict[str, Any] = {}
    for line in frontmatter.splitlines():
        if not line.strip() or line.startswith(" ") or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        clean_key = key.strip()
        clean_value = value.strip()
        if clean_key in {"description", "compatibility", "license", "allowed-tools"} and not clean_value.startswith(("'", '"', ">", "|")) and re.search(r"\S.*:\s", clean_value):
            findings.append(
                Finding(
                    "error",
                    "frontmatter",
                    f"Unquoted frontmatter value for '{clean_key}' contains ': ' and may not parse as YAML.",
                    str(skill_md),
                    "Quote the value or use a folded block scalar before sharing the skill.",
                )
            )
        metadata[clean_key] = clean_value.strip('"').strip("'")

    return metadata, parts[2], findings


def check_frontmatter(skill_dir: Path, skill_md: Path) -> list[Finding]:
    metadata, _body, findings = parse_frontmatter(skill_md)
    if any(finding.level == "error" and finding.check == "frontmatter" for finding in findings):
        return findings

    raw_name = metadata.get("name", "")
    raw_description = metadata.get("description", "")
    name = raw_name if isinstance(raw_name, str) else ""
    description = raw_description if isinstance(raw_description, str) else ""

    if raw_name and not isinstance(raw_name, str):
        findings.append(Finding("error", "name", "Frontmatter field 'name' must be a string.", str(skill_md)))
    if raw_description and not isinstance(raw_description, str):
        findings.append(Finding("error", "description", "Frontmatter field 'description' must be a string.", str(skill_md)))

    if not name:
        findings.append(Finding("error", "name", "Missing required frontmatter field: name.", str(skill_md)))
    else:
        if len(name) > MAX_NAME_LENGTH:
            findings.append(Finding("error", "name", f"Skill name exceeds {MAX_NAME_LENGTH} characters.", str(skill_md)))
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            findings.append(Finding("error", "name", "Skill name should be lowercase kebab-case with no leading/trailing/consecutive hyphens.", str(skill_md)))
        if skill_dir.name != name:
            findings.append(Finding("warning", "name", f"Directory name '{skill_dir.name}' does not match skill name '{name}'. Some clients require a match.", str(skill_md)))

    if not description:
        findings.append(Finding("error", "description", "Missing required frontmatter field: description.", str(skill_md)))
    else:
        if len(description) > MAX_DESCRIPTION_LENGTH:
            findings.append(Finding("error", "description", f"Description exceeds {MAX_DESCRIPTION_LENGTH} characters.", str(skill_md)))
        if "use when" not in description.lower() and "use this skill when" not in description.lower():
            findings.append(Finding("warning", "description", "Description may not clearly say when to use the skill.", str(skill_md), "Add trigger contexts and near-boundary wording."))
        if re.search(r"\b(I can|you can use)\b", description, re.IGNORECASE):
            findings.append(Finding("warning", "description", "Description should be third-person, not first/second-person.", str(skill_md)))

    return findings


def check_markdown_structure(skill_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    nested_skill_files = [path for path in sorted(skill_dir.rglob("SKILL.md")) if path != skill_dir / "SKILL.md"]
    for nested_skill_file in nested_skill_files:
        findings.append(
            Finding(
                "warning",
                "nested-skill",
                "Nested SKILL.md files may be discovered as separate real skills. Use SKILL.fixture.md plus eval source/target mapping for fixtures.",
                str(nested_skill_file.relative_to(skill_dir)),
            )
        )

    markdown_files = [skill_dir / "SKILL.md", *sorted((skill_dir / "references").glob("*.md"))]

    for markdown_file in markdown_files:
        if not markdown_file.exists():
            continue
        text = markdown_file.read_text(encoding="utf-8")
        lines = text.splitlines()
        relative_path = str(markdown_file.relative_to(skill_dir))

        if markdown_file.name == "SKILL.md" and len(lines) > MAX_SKILL_LINES:
            findings.append(Finding("warning", "size", f"SKILL.md has {len(lines)} lines; keep under {MAX_SKILL_LINES} and move details to references.", relative_path))

        if markdown_file.parent.name == "references" and len(lines) > LONG_REFERENCE_LINES:
            first_section = "\n".join(lines[:30]).lower()
            if "## contents" not in first_section:
                findings.append(Finding("warning", "toc", f"Reference file has {len(lines)} lines and should include a table of contents near the top.", relative_path))

        if WINDOWS_PATH_PATTERN.search(text):
            findings.append(Finding("warning", "paths", "Use Linux-style forward slashes in skill paths; backslash paths break in the target environment.", relative_path))

        for matched_link in LOCAL_LINK_PATTERN.findall(text):
            link_target = matched_link.split("#", 1)[0].strip()
            if not link_target or re.match(r"^[a-z]+://", link_target) or link_target.startswith("mailto:"):
                continue
            target_path = (markdown_file.parent / link_target).resolve()
            try:
                target_path.relative_to(skill_dir.resolve())
            except ValueError:
                continue
            if not target_path.exists():
                findings.append(Finding("error", "links", f"Broken local link: {matched_link}", relative_path))

        open_fence: int | None = None
        for line_number, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("```"):
                tick_count = len(stripped) - len(stripped.lstrip("`"))
                if open_fence is None:
                    open_fence = tick_count
                elif tick_count >= open_fence:
                    open_fence = None
        if open_fence is not None:
            findings.append(Finding("error", "markdown", "Unclosed fenced code block.", relative_path))

    return findings


def remove_fenced_blocks(markdown_text: str) -> str:
    lines: list[str] = []
    open_fence: int | None = None
    for line in markdown_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```"):
            tick_count = len(stripped) - len(stripped.lstrip("`"))
            if open_fence is None:
                open_fence = tick_count
            elif tick_count >= open_fence:
                open_fence = None
            continue
        if open_fence is None:
            lines.append(line)
    return "\n".join(lines)


def normalize_heading(heading_text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", heading_text.lower()).strip()


def remove_sections(markdown_text: str, headings_to_remove: set[str]) -> str:
    normalized_headings = {normalize_heading(heading) for heading in headings_to_remove}
    kept_lines: list[str] = []
    skipped_heading_level: int | None = None

    for line in markdown_text.splitlines():
        heading_match = re.match(r"^(#{2,6})\s+(.+?)\s*$", line)
        if heading_match:
            heading_level = len(heading_match.group(1))
            heading_text = normalize_heading(heading_match.group(2))
            if skipped_heading_level is not None and heading_level <= skipped_heading_level:
                skipped_heading_level = None
            if skipped_heading_level is None and heading_text in normalized_headings:
                skipped_heading_level = heading_level
                continue

        if skipped_heading_level is None:
            kept_lines.append(line)

    return "\n".join(kept_lines)


def check_instruction_quality(skill_dir: Path) -> list[Finding]:
    skill_md = skill_dir / "SKILL.md"
    raw_text = skill_md.read_text(encoding="utf-8")
    text_without_code = remove_fenced_blocks(raw_text)
    lower_text = text_without_code.lower()
    hint_text = remove_sections(text_without_code, {"Common Anti-Patterns", "Example: Before and After"}).lower()
    findings: list[Finding] = []

    if "## gotchas" not in lower_text:
        findings.append(Finding("info", "gotchas", "No Gotchas section found. Add one if the skill has non-obvious failure modes.", "SKILL.md"))
    if "validat" not in lower_text and "verify" not in lower_text:
        findings.append(Finding("warning", "validation", "No validation/verification loop detected.", "SKILL.md", "Add a command, checklist, or rubric that lets the agent check its work."))
    if "```" not in raw_text and "script" in lower_text:
        findings.append(Finding("info", "examples", "Skill mentions scripts but has no command examples.", "SKILL.md"))

    for hint, message in ANTI_PATTERN_HINTS.items():
        if hint in hint_text:
            findings.append(Finding("info", "anti-pattern", message, "SKILL.md"))

    return findings


def check_eval_files(skill_dir: Path, create_evals: bool) -> list[Finding]:
    findings: list[Finding] = []
    evals_dir = skill_dir / "evals"
    trigger_file = evals_dir / "trigger-queries.json"
    output_file = evals_dir / "output-evals.json"

    if create_evals:
        evals_dir.mkdir(exist_ok=True)
        metadata, _body, _findings = parse_frontmatter(skill_dir / "SKILL.md")
        skill_name = metadata.get("name", "replace-with-skill-name")
        if not trigger_file.exists():
            trigger_data = {**TRIGGER_TEMPLATE, "skill_name": skill_name}
            trigger_file.write_text(json.dumps(trigger_data, indent=2) + "\n", encoding="utf-8")
            findings.append(Finding("info", "evals", "Created trigger eval template.", str(trigger_file.relative_to(skill_dir))))
        if not output_file.exists():
            output_data = {**OUTPUT_TEMPLATE, "skill_name": skill_name}
            output_file.write_text(json.dumps(output_data, indent=2) + "\n", encoding="utf-8")
            findings.append(Finding("info", "evals", "Created output eval template.", str(output_file.relative_to(skill_dir))))

    if not trigger_file.exists():
        findings.append(Finding("warning", "evals", "Missing evals/trigger-queries.json.", None, "Create should-trigger and near-miss prompts."))
    else:
        findings.extend(validate_json_file(trigger_file, "trigger evals"))

    if not output_file.exists():
        findings.append(Finding("warning", "evals", "Missing evals/output-evals.json.", None, "Create realistic output-quality test cases with assertions."))
    else:
        findings.extend(validate_json_file(output_file, "output evals"))

    return findings


def contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return any(placeholder.lower() in value.lower() for placeholder in PLACEHOLDER_TEXT)
    if isinstance(value, list):
        return any(contains_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(contains_placeholder(item) for item in value.values())
    return False


def validate_json_file(path: Path, label: str) -> list[Finding]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [Finding("error", "evals", f"Invalid JSON in {label}: {error}", str(path))]

    findings: list[Finding] = []
    if contains_placeholder(data):
        findings.append(Finding("warning", "evals", f"{label} still contains generated placeholder text; replace it with realistic eval content.", str(path)))
    return findings


def check_generated_artifacts(skill_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    eval_runs_dir = skill_dir / "evals" / "runs"
    if eval_runs_dir.exists():
        findings.append(
            Finding(
                "warning",
                "artifacts",
                "Eval run artifacts should usually not be committed with the skill.",
                str(eval_runs_dir.relative_to(skill_dir)),
                "Move or remove evals/runs before sharing or packaging the skill.",
            )
        )
    for path in sorted(skill_dir.rglob("*")):
        if path.name in GENERATED_ARTIFACT_NAMES or path.suffix in GENERATED_ARTIFACT_SUFFIXES:
            relative_path = str(path.relative_to(skill_dir))
            findings.append(Finding("warning", "artifacts", "Generated/cache artifact should not be committed with the skill.", relative_path, "Remove it before sharing or packaging the skill."))
    return findings


def manual_workflow(skill_dir: Path) -> list[str]:
    script_path = Path(__file__).resolve()
    eval_runner_path = script_path.with_name("run-skill-evals.py")
    return [
        f"Run automated trigger/output evals when pi/model access is available: python {eval_runner_path} {skill_dir} --mode all",
        "Open the generated evals/runs/<timestamp>/review.md. It lists exact stdout/stderr, session logs, workspaces, changed-file summaries, assertions, and manual-review items.",
        "For failed or surprising trigger evals, inspect sessions/**/*.jsonl and confirm whether a tool call read the target SKILL.md; adjust the description boundary from that evidence.",
        "For output evals, compare with_skill vs baseline outputs and grade each assertion with PASS/FAIL plus concrete evidence. Use --llm-judge for a draft, but verify subjective or trace-based PASS grades manually.",
        "Read execution traces. Note wasted steps, missed references, ignored gotchas, over-broad activation, or copied documentation. Convert each real correction into a skill edit.",
        "Test on each model/client you expect to support. If weaker models fail, add the minimum extra guidance; if stronger models waste context, cut redundant explanation.",
        f"After editing, rerun this script: python {script_path} {skill_dir}",
    ]


def run_checks(skill_dir: Path, create_evals: bool) -> Report:
    findings: list[Finding] = []
    if not skill_dir.exists() or not skill_dir.is_dir():
        findings.append(Finding("error", "path", "Skill path must be an existing directory.", str(skill_dir)))
        return Report(str(skill_dir), False, findings, [])

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        findings.append(Finding("error", "structure", "Missing SKILL.md.", str(skill_dir)))
        return Report(str(skill_dir), False, findings, [])

    findings.extend(check_frontmatter(skill_dir, skill_md))
    findings.extend(check_markdown_structure(skill_dir))
    findings.extend(check_instruction_quality(skill_dir))
    findings.extend(check_eval_files(skill_dir, create_evals))
    findings.extend(check_generated_artifacts(skill_dir))

    passed = not any(finding.level == "error" for finding in findings)
    return Report(str(skill_dir), passed, findings, manual_workflow(skill_dir))


def print_text_report(report: Report) -> None:
    status = "PASS" if report.passed else "FAIL"
    print(f"# Skill test report: {status}")
    print(f"Skill: {report.skill_path}\n")

    if report.findings:
        print("## Automated findings")
        for finding in report.findings:
            location = f" ({finding.path})" if finding.path else ""
            print(f"- [{finding.level.upper()}] {finding.check}{location}: {finding.message}")
            if finding.manual_next_step:
                print(f"  Manual next step: {finding.manual_next_step}")
        print()
    else:
        print("## Automated findings\n- No findings.\n")

    print("## Manual / semi-automated workflow")
    for index, step in enumerate(report.manual_workflow, 1):
        print(f"{index}. {step}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run universal static checks and generate manual eval instructions for an Agent Skill.")
    parser.add_argument("skill_dir", type=Path, help="Path to the skill directory containing SKILL.md")
    parser.add_argument("--create-evals", action="store_true", help="Create evals/trigger-queries.json and evals/output-evals.json templates if missing")
    parser.add_argument("--json", action="store_true", help="Output the report as JSON")
    args = parser.parse_args()

    report = run_checks(args.skill_dir.resolve(), args.create_evals)
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print_text_report(report)
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
