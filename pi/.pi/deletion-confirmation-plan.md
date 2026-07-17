# File-deletion confirmation implementation plan

## Decisions

- Treat this as a best-effort gate for known deletion commands, not a complete filesystem security boundary.
- Use `unbash@4.0.3`: a synchronous, typed, zero-dependency Bash AST parser. It represents redirections, brace expansion, substitutions, and quoted/unquoted heredocs.
- Treat `unbash` syntax problems as `ast.errors`; the parser is tolerant and normally returns a partial AST rather than throwing.
- Support TUI confirmation only. RPC, print, and JSON modes fail closed without attempting UI.
- Default destructive prompts to No and approve only an exact affirmative selection.
- Aggregate assessments with `deletion > unknown > safe`. A deletion found in a script that also has a parse error is still `deletion`.

## 1. Restructure the extension

Convert the 944-line file into a directory extension:

```text
agent/extensions/confirm-file-deletion/
├── index.ts
├── assessment.ts
├── ast-traversal.ts
├── command-policies.ts
├── package.json
├── package-lock.json
├── tsconfig.json
└── README.md
```

Move tests into corresponding files:

```text
agent/tests/confirm-file-deletion/
├── assessment.test.ts
├── command-policies.test.ts
└── extension.test.ts
```

Configure the extension package as private ESM and pin dependencies exactly:

- Runtime dependency: `unbash@4.0.3`.
- Development dependencies: `@earendil-works/pi-coding-agent@0.80.10`, `typescript@5.9.3`, and `@types/node@24.12.4`.
- Add `test` and `check` scripts for the relocated tests and `tsc --noEmit`.

The Pi package is a development dependency because `index.ts` imports `isToolCallEventType` at runtime and standalone `node --test` must be able to resolve it. Pi itself supplies that package when loading the extension normally. Document that the pinned development version should be updated alongside Pi.

Install reproducibly with:

```sh
npm ci --prefix agent/extensions/confirm-file-deletion
```

## 2. Define an explainable classification result

Replace the internal boolean with structured findings:

```ts
type AssessmentFinding = {
  kind: "deletion" | "unknown";
  policy: string;
  message: string;
  span?: { start: number; end: number };
};

type DeletionAssessment =
  | { kind: "safe" }
  | { kind: "deletion"; findings: AssessmentFinding[] }
  | { kind: "unknown"; findings: AssessmentFinding[] };
```

Use stable `policy` identifiers in tests and human-readable `message` values in prompts. Normalize `unbash`'s `pos`/`end` offsets into `span` when available.

Aggregate all visited results using this precedence:

1. Any deletion finding produces `kind: "deletion"`, even when unknown findings or parse errors also exist.
2. Otherwise, any unknown finding produces `kind: "unknown"`.
3. Otherwise, the result is `kind: "safe"`.

Examples:

- A malformed script whose recovered AST contains `rm obsolete.txt` is `deletion`.
- A malformed script with no detected deletion is `unknown`.
- An unexpected parser exception is caught and becomes `unknown`.

Policy at the extension boundary:

- `deletion` → request confirmation.
- `unknown` → request confirmation.
- `safe` → continue without prompting.

Preserve `isFileDeletionCommand()` temporarily as a compatibility wrapper. It returns `assessment.kind !== "safe"`, so unknown input remains fail-closed. Keep only a small compatibility test set; new tests should exercise the richer assessment API directly.

## 3. Write behavioral and regression tests first

Add currently failing deletion cases:

```sh
>/tmp/log rm obsolete.txt
sudo 2>/dev/null rm obsolete.txt
rm {old,new}.txt
rm -
timeout 5 rm obsolete.txt
env -S'rm obsolete.txt'
xargs -0I ITEM rm ITEM
cat <<EOF
$(rm obsolete.txt)
EOF
```

Add non-deletion cases:

```sh
rm >/tmp/log
shred -u
cat <<'EOF'
$(rm obsolete.txt)
EOF
program=printf; "$program" safe
```

Use table-driven tests with real shell source. For each case, assert the assessment kind and stable finding policy rather than exact prose. Retain the full existing command corpus while splitting tests by behavior.

Add focused coverage for:

- Parse errors with and without a recovered deletion, proving `deletion > unknown`.
- Command/process substitutions, arithmetic command substitutions, subshells, brace groups, coprocesses, functions, pipelines, conditionals, loops, and case arms.
- Quoted versus unquoted heredoc bodies.
- Redirect targets and assignment values containing substitutions.
- Wrapper recursion and option combinations, including malformed or unsupported options.
- Nested `eval`, interpreter command strings, `env -S`, `find -exec`, and `xargs` dispatch.
- Dynamic command names, stale assignment invalidation, shell assignment scope, and control-flow boundaries.
- Assessment limits and unexpected parser failures, all of which must fail closed.

For extension integration, cover both `tool_call` and `user_bash`:

- Exact affirmative selection allows execution.
- The first/default No option, Escape/`undefined`, unexpected selector values, and selector exceptions block.
- Findings are included in the prompt.
- TUI with unavailable UI blocks.
- RPC, JSON, and print modes block without invoking any UI method.
- Non-deletion commands do not prompt.
- Non-Bash tool calls are ignored.
- Existing blocked tool-call and user-Bash result shapes remain unchanged.

The extension integration test must import `index.ts` normally. This verifies that runtime imports, including `isToolCallEventType`, resolve under the documented `npm ci` setup.

## 4. Implement bounded AST traversal

Create pure, exhaustive visitors for:

- Scripts, statements, and compound lists.
- Pipelines and `&&`/`||` lists.
- Conditionals, loops, functions, and case arms.
- Subshells, brace groups, and coprocesses.
- Command and process substitutions.
- Arithmetic command substitutions.
- Unquoted heredoc bodies.
- Assignment values, command words, arguments, and redirect targets.

Quoted heredocs must not be traversed because their contents are literal. Treat all branches and function bodies as potentially executable; this is intentionally conservative and may prompt for unreachable code.

Use a shared traversal/recursive-assessment budget with documented defaults:

- Maximum top-level source length: 128 KiB.
- Maximum aggregate source parsed through nested command strings: 512 KiB.
- Maximum recursive command-string depth: 32.
- Maximum visited AST/word nodes: 50,000.
- Maximum collected findings: 100.

Exceeding any limit returns `unknown` unless a deletion has already been found, in which case aggregation keeps the result as `deletion`. Catch unexpected parser or traversal exceptions and convert them to unknown findings. Allow tests to inject smaller limits so every boundary is deterministic and inexpensive to test.

## 5. Implement explicit command policies

Keep CLI semantics separate from shell parsing. Each policy returns safe, deletion, unknown, or no match plus structured findings.

Policies should cover:

- Direct deletion: `rm`, `rmdir`, `unlink`.
- Conditional deletion: `shred --remove`.
- Search execution: `find -delete`, `-exec`, `-execdir`, `-ok`, `-okdir`.
- Dispatchers: `xargs`, BusyBox, ToyBox.
- Git: `git clean`, `git rm`.
- Synchronization: `rsync --delete*`, `--remove-source-files`.
- Shell command strings: `bash`, `sh`, `dash`, `ksh`, `mksh`, and `zsh` with `-c`/equivalent options.
- Shell evaluation: `eval` with literal command text.
- Wrappers: `sudo`, `doas`, `env`, `command`, `exec`, `nice`, `nohup`, `setsid`, external `time`, and `timeout`.

Treat Bash parsing of `sh`, `dash`, `ksh`, `mksh`, and `zsh` command strings as a documented conservative approximation. Treat unsupported interpreter dialects such as `fish -c` as `unknown` rather than parsing them as Bash. Interpreter script files such as `bash script.sh` remain in the documented arbitrary-script exclusion.

Each policy needs its own option parser, including:

- Short-option clusters such as `-0I`.
- Attached values such as `-Scommand` and `-IITEM`.
- Long options with `=`.
- `--` terminators.
- Options whose arguments may begin with `-`.
- Informational and dry-run modes that guarantee no execution.
- Real operands, including a lone `-`.
- Required positional wrapper operands, such as the duration consumed by `timeout`.
- Recursive wrapper/dispatcher chains.

Once a known policy or wrapper matches, malformed syntax, unsupported options that make command location ambiguous, dynamic command strings, or missing required option values produce `unknown`, not `safe`. Known help/version/dry-run forms are safe only where the CLI guarantees that trailing command-like operands will not execute.

Match command policies by basename, including absolute paths, and document the resulting conservative false positives for unrelated executables that reuse names such as `rm`.

An unrecognized literal top-level command remains safe/out of scope under the best-effort model. Do not attempt to recognize Python, Node, Ruby, sourced files, or arbitrary executable scripts; document these exclusions prominently.

## 6. Handle dynamic command names without stale state

Implement limited constant resolution for straight-line assignments:

```sh
program=printf; "$program" safe       # safe
deleter=rm; "$deleter" obsolete.txt   # deletion
```

A resolvable literal may contain only statically evaluable quoted/unquoted literal fragments. Parameter expansion, command substitution, arithmetic expansion, globbing, or other computed content makes the value unknown.

State rules:

- Assignment-only commands update straight-line state.
- Assignment prefixes on a command do not persist and do not affect expansions performed for that same command; use the incoming value.
- A non-literal reassignment invalidates the previous constant.
- `unset` invalidates the named constant.
- Supported assignment builtins such as `export`, `readonly`, `declare`, `typeset`, and `local` either update literal values correctly or invalidate affected names.
- At unsupported mutation or control-flow joins, clear affected state rather than retaining a possibly stale value.
- Analyze branches from independent copies of incoming state and do not merge branch-local values.
- Do not propagate state out of pipelines, functions, loops, or subshells.

Required regressions include:

```sh
program=printf; program=$unknown; "$program" safe  # unknown, not stale printf
program=printf; unset program; "$program" safe    # unknown
```

Unknown environment values or unresolved command names produce `unknown` and therefore require confirmation.

## 7. Simplify and fail-close the Pi integration

Gate mode and UI availability in the event handlers before calling a small confirmation helper:

```ts
const choice = await ctx.ui.select(prompt, [
  "No, block it",
  "Yes, allow deletion",
]);
```

The No option must be first so Enter defaults to blocking. Approve only the exact string `"Yes, allow deletion"`; `undefined`, any unexpected value, or an exception blocks.

Include concise, deduplicated assessment findings in the prompt so users can distinguish direct deletion, nested dispatch, dynamic-command uncertainty, parser errors, and limit failures.

Remove:

- `rpcConfirmationTimeoutMs`.
- RPC-specific timeout behavior and tests.
- The mode parameter from the confirmation helper itself.

For `ctx.mode !== "tui"` or `!ctx.hasUI`, block with the existing unavailable-confirmation reason without calling `select`. Continue catching UI failures so agent Bash and `user_bash` both fail closed.

Use `isToolCallEventType("bash", event)` instead of casting tool input. Keep the host package available as a pinned development dependency so this runtime import works in standalone tests.

## 8. Remove the handwritten parser and document scope

Once the AST implementation passes the complete old and new corpus:

- Delete tokenization, comment/heredoc preprocessing, substitution scanners, and shell segmentation.
- Remove the original `confirm-file-deletion.ts` so Pi does not load duplicate extensions.
- Remove the old test files after their cases have moved to the new suite.
- Preserve current user-facing blocked-result shapes.
- Document the policy list, basename matching, Bash-dialect approximation, arbitrary-script exclusions, fail-closed unknown behavior, assessment limits, dependency installation, and TUI-only confirmation in the README.

## 9. Validation

Run from the repository root:

```sh
npm ci --prefix agent/extensions/confirm-file-deletion
npm --prefix agent/extensions/confirm-file-deletion run check
npm --prefix agent/extensions/confirm-file-deletion test
git diff --check
```

Also confirm that no original extension or old test files remain and that only the directory extension is discoverable.

Manually verify Pi integration:

1. Enter on the selector defaults to blocking.
2. Escape blocks.
3. Explicit approval runs the command.
4. The prompt displays the relevant findings.
5. Agent Bash and user `!bash` paths behave identically.
6. RPC, print, and JSON modes block without attempting UI.
7. `/reload` discovers only the new directory extension.

## Suggested commit sequence

1. Add the assessment contract, package/test configuration, and failing regression tests.
2. Add `unbash`, bounded AST traversal, and assessment aggregation.
3. Port and improve command policies.
4. Add dynamic command resolution and invalidation.
5. Replace TUI confirmation and remove RPC behavior.
6. Delete the handwritten parser and old tests, then document scope and limits.
