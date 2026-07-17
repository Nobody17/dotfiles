# File-deletion confirmation

A best-effort Pi extension that asks before known Bash commands may delete files. It is a confirmation gate, **not** a filesystem security boundary.

## Install and validate

```sh
npm ci --prefix agent/extensions/confirm-file-deletion
npm --prefix agent/extensions/confirm-file-deletion run check
npm --prefix agent/extensions/confirm-file-deletion test
```

`unbash@4.0.3` is the runtime Bash AST parser. The pinned development copy of `@earendil-works/pi-coding-agent` makes the standalone Node tests resolve Pi's runtime import; update that pin when Pi is updated.

Pi discovers this directory extension at `agent/extensions/confirm-file-deletion/index.ts`.

## Behaviour

- Only TUI mode can approve an assessment. RPC, JSON, print mode, missing UI, cancelled dialogs, unexpected selections, and UI errors all block execution.
- The selector puts **No, block it** first. Only the exact **Yes, allow deletion** selection approves.
- `tool_call` blocks use Pi's normal `{ block, reason }` result. User `!bash` blocks preserve the normal failed Bash-result shape.
- Prompts include deduplicated assessment findings, such as direct removal, parser failure, dynamic command names, and limits.

## Detection scope

The parser walks Bash statements, pipelines, logical lists, conditionals, loops, functions, case arms, subshells, brace groups, coprocesses, substitutions, arithmetic command substitutions, assignments, redirect targets, and unquoted heredocs. Quoted heredocs are literal and are deliberately skipped.

Known policies include:

- `rm`, `rmdir`, `unlink`, and `shred --remove`
- `find -delete` and `find -exec`/`-execdir`/`-ok`/`-okdir`
- `xargs`, BusyBox, ToyBox, `git clean`, `git rm`, and destructive `rsync` options
- `bash`, `sh`, `dash`, `ksh`, `mksh`, and `zsh` command strings; `eval`; and `env -S`
- wrappers: `command`, `sudo`, `doas`, `env`, `exec`, `nice`, `nohup`, `setsid`, external `time`, and `timeout`

Policy matching uses a command basename, so an unrelated executable named `rm` is conservatively treated as `rm`. Bash parsing is also a conservative approximation for POSIX shells and Zsh command strings.

Unrecognised literal commands are out of scope. In particular, this extension does not inspect arbitrary scripts or `source` files, or code passed to Python, Node, Ruby, and similar interpreters. An unsupported interpreter command string (for example `fish -c`) is instead classified as unknown and requires confirmation.

Straight-line literal assignments can resolve a command name (`deleter=rm; "$deleter" file`). Computed names, stale values after dynamic reassignment or `unset`, and unsafe control-flow joins become unknown and require confirmation.

## Fail-closed assessment

A result is `safe`, `deletion`, or `unknown`. Unknown parser input, malformed known-wrapper syntax, unresolved command names, parser exceptions, and exhausted limits all require confirmation. A recovered deletion always wins over unknown findings.

The default bounds are:

| Limit | Default |
| --- | ---: |
| Top-level source | 128 KiB |
| Aggregate nested command strings | 512 KiB |
| Nested command-string depth | 32 |
| Visited AST and word nodes | 50,000 |
| Collected findings | 100 |

The exported `isFileDeletionCommand()` compatibility function remains fail-closed and returns `true` for both deletion and unknown assessments. New callers should use `assessFileDeletion()` for findings.
