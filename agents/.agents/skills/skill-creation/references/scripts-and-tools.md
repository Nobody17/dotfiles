---
name: scripts-and-tools
description: How to use one-off commands, bundle reusable scripts, and design scripts for agentic use.
---

# Scripts & Tools

## Contents

- [One-Off Commands](#one-off-commands)
- [Referencing Scripts from SKILL.md](#referencing-scripts-from-skillmd)
- [Self-Contained Scripts](#self-contained-scripts)
- [Designing Scripts for Agentic Use](#designing-scripts-for-agentic-use)
- [MCP tool references](#mcp-tool-references)
- [Runtime and dependency assumptions](#runtime-and-dependency-assumptions)
- [Solve, don't punt](#solve-dont-punt)

Skills can instruct agents to run shell commands and bundle reusable scripts in a `scripts/` directory.

## One-Off Commands

When an existing package already does what you need, reference it directly without a `scripts/` directory:

| Tool | Example | Notes |
|------|---------|-------|
| `uvx` | `uvx ruff@0.8.0 check .` | Runs Python packages in isolated envs. Fast, aggressive caching. Requires uv. |
| `pipx` | `pipx run 'black==24.10.0' .` | Mature alternative to uvx. Available via OS package managers. |
| `npx` | `npx eslint@9 --fix .` | Ships with Node.js. Downloads, runs, caches. |
| `bunx` | `bunx eslint@9 --fix .` | Bun's equivalent of npx. Only in Bun environments. |
| `deno run` | `deno run npm:create-vite@6` | Runs directly from URLs/specifiers. Requires permission flags. |
| `go run` | `go run golang.org/x/tools/cmd/goimports@v0.28.0 .` | Built into Go. Pin versions explicitly. |

**Tips:**
- **Pin versions** (`eslint@9.0.0`) so commands behave the same over time.
- **State prerequisites** in SKILL.md or `compatibility` (e.g., "Requires Node.js 18+"). Do not assume tools are installed.
- **Move complex commands to scripts.** A one-off works for simple invocations. When a command grows complex enough to be hard to get right on the first try, a tested script is more reliable.

## Referencing Scripts from SKILL.md

Use **relative paths from the skill directory root**. List available scripts so the agent knows they exist:

```markdown
## Available scripts

- **`scripts/validate.sh`** — Validates configuration files
- **`scripts/process.py`** — Processes input data
```

Then instruct the agent to run them:
```markdown
1. Run validation: `bash scripts/validate.sh "$INPUT_FILE"`
2. Process results: `python3 scripts/process.py --input results.json`
```

Make clear whether the agent should **execute** the script (most common) or **read it as reference** (for complex logic).

## Self-Contained Scripts

Bundle scripts that declare their own dependencies inline — no separate manifest or install step needed.

### Python (PEP 723)

Declare dependencies in a TOML block inside `# ///` markers:

```python
# /// script
# dependencies = [
#   "beautifulsoup4>=4.12,<5",
# ]
# ///

from bs4 import BeautifulSoup
# ... script logic
```

Run with: `uv run scripts/extract.py` or `pipx run scripts/extract.py`

- Pin versions with PEP 508 specifiers.
- Use `requires-python` to constrain the Python version.
- Use `uv lock --script` for a lockfile (full reproducibility).

### Deno

Deno's `npm:` and `jsr:` import specifiers make every script self-contained:

```typescript
import * as cheerio from "npm:cheerio@1.0.0";
// ... script logic
```

Run with: `deno run scripts/extract.ts`

- Use `npm:` for npm packages, `jsr:` for Deno-native.
- Dependencies cached globally. Use `--reload` to force re-fetch.
- Packages with native addons (node-gyp) may not work.

### Bun

Bun auto-installs missing packages at runtime. Pin versions directly in imports:

```typescript
import * as cheerio from "cheerio@1.0.0";
// ... script logic
```

Run with: `bun run scripts/extract.ts`

- No `package.json` or `node_modules` needed. TypeScript works natively.
- If a `node_modules` directory exists up the tree, auto-install is disabled.

## Designing Scripts for Agentic Use

Agents read stdout and stderr to decide what to do next. These design choices make scripts dramatically easier for agents to use.

### Avoid interactive prompts

This is a **hard requirement**. Agents operate in non-interactive shells — they cannot respond to TTY prompts. A script that blocks on input hangs indefinitely.

Accept all input via command-line flags, environment variables, or stdin:
```
# Bad: hangs
$ python scripts/deploy.py
Target environment: _

# Good: clear error with guidance
$ python scripts/deploy.py
Error: --env is required. Options: development, staging, production.
Usage: python scripts/deploy.py --env staging --tag v1.2.3
```

### Document usage with `--help`

`--help` output is the primary way an agent learns your script's interface:
```
Usage: scripts/process.py [OPTIONS] INPUT_FILE

Process input data and produce a summary report.

Options:
  --format FORMAT    Output format: json, csv, table (default: json)
  --output FILE      Write output to FILE instead of stdout
  --verbose          Print progress to stderr

Examples:
  scripts/process.py data.csv
  scripts/process.py --format csv --output report.csv data.csv
```

Keep it concise — the output enters the agent's context window.

### Write helpful error messages

Say what went wrong, what was expected, and what to try:
```
Error: --format must be one of: json, csv, table.
       Received: "xml"
```

### Use structured output

Prefer JSON, CSV, or TSV over free-form text. Structured formats can be consumed by both the agent and standard tools (`jq`, `cut`, `awk`).

**Separate data from diagnostics:** structured data to stdout, progress/warnings to stderr.

### Further considerations

- **Idempotency.** Agents may retry commands. "Create if not exists" > "create and fail on duplicate."
- **Input constraints.** Reject ambiguous input with a clear error. Use enums and closed sets.
- **Dry-run support.** For destructive operations, a `--dry-run` flag lets the agent preview what will happen.
- **Meaningful exit codes.** Use distinct codes for different failures (not found, invalid args, auth) and document in `--help`.
- **Safe defaults.** Consider `--confirm` or `--force` flags for destructive operations.
- **Predictable output size.** Many agent harnesses truncate tool output. Default to summaries or reasonable limits; support `--offset` for pagination or `--output -` to explicitly opt into stdout for large output.
- **No voodoo constants.** Every configuration value should be justified and self-documenting. If you don't know the right value, how will the agent determine it?

## MCP tool references

If a skill instructs the agent to use MCP tools, use fully qualified names to avoid ambiguity: `ServerName:tool_name`. This matters when multiple servers expose similar tools.

```markdown
Use `BigQuery:query` for warehouse queries and `GitHub:create_issue` for issue creation.
```

## Runtime and dependency assumptions

State what the target client can and cannot do. Some environments allow package installation and network access; others run skills without network access. If the skill requires a package, system tool, credential, browser, or network connection, list it explicitly in `SKILL.md` or `compatibility` and provide a fallback when possible.

## Solve, don't punt

Handle error conditions explicitly rather than punting to the agent:

```python
# Good: handles the error
if not os.path.exists(input_path):
    print(f"Error: Input file '{input_path}' not found.", file=sys.stderr)
    print("Provide a valid path or create the file first.", file=sys.stderr)
    sys.exit(1)

# Bad: punts to the agent
try:
    process(input_path)
except Exception as e:
    print(f"Error: {e}")  # agent has to figure out what went wrong
```

<!--
Source references:
- https://github.com/agentskills/agentskills/blob/main/docs/skill-creation/using-scripts.mdx
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#advanced-skills-with-executable-code
-->
