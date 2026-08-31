import { parse, type Script, type Word } from "unbash";

import { basename, literalWordValue } from "./command-policies.ts";

const directDeletionCommands = new Set(["rm", "rmdir", "unlink"]);

/** Cap on brace-expansion results; larger expansions require confirmation. */
const maxBraceExpansions = 2000;
/** Cap on brace nesting depth; deeper expansions require confirmation. */
const maxBraceDepth = 6;

type ParsedScript = Script & { errors?: Array<unknown> };

type BraceContentResult =
  | { kind: "literal" } // no expansion: braces stay as-is at runtime
  | { kind: "alternatives"; alternatives: string[] }
  | { kind: "error" }; // expansion happens but cannot be enumerated safely

/**
 * Renders a word as literal text, accepting brace expansion parts as their raw
 * text (bash expands them later). Any dynamic content (parameter, command, or
 * arithmetic expansion) makes the operand unresolvable and returns undefined.
 */
function deletionOperandValue(word: Word): string | undefined {
  if (word.parts === undefined) return word.value;
  return partsLiteralText(word.parts);
}

function partsLiteralText(parts: Word["parts"]): string | undefined {
  let value = "";
  for (const part of parts ?? []) {
    if (part.type === "Literal" || part.type === "SingleQuoted" || part.type === "AnsiCQuoted") {
      value += part.value;
      continue;
    }
    if (part.type === "BraceExpansion") {
      value += part.text;
      continue;
    }
    if (part.type === "DoubleQuoted" || part.type === "LocaleString") {
      const child = partsLiteralText(part.parts);
      if (child === undefined) return undefined;
      value += child;
      continue;
    }
    return undefined;
  }
  return value;
}

function directDeletionOperands(argumentsList: Word[]): string[] | undefined {
  let optionsEnded = false;
  const operands: string[] = [];

  for (const word of argumentsList) {
    const value = deletionOperandValue(word);
    if (value === undefined) return undefined;

    if (!optionsEnded && value === "--") {
      optionsEnded = true;
      continue;
    }
    if (!optionsEnded && value.startsWith("-") && value !== "-") continue;

    operands.push(value);
  }

  return operands;
}

function findUnescapedOpenBrace(path: string): number {
  for (let index = 0; index < path.length; index += 1) {
    if (path[index] !== "{") continue;
    let backslashes = 0;
    for (let cursor = index - 1; cursor >= 0 && path[cursor] === "\\"; cursor -= 1) backslashes += 1;
    if (backslashes % 2 === 0) return index;
  }
  return -1;
}

function findMatchingCloseBrace(path: string, open: number): number {
  let depth = 0;
  for (let index = open; index < path.length; index += 1) {
    const character = path[index];
    if (character === "\\") {
      index += 1;
      continue;
    }
    if (character === "{") depth += 1;
    else if (character === "}") {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  return -1;
}

/**
 * Classifies the text between an unescaped `{` and its matching `}`.
 *
 * Only comma-separated alternations need enumeration: they can introduce
 * arbitrary path text (including `..`, `/`, or empty alternatives) that must
 * be re-validated per result. Bash ranges (`{a..e}`, `{1..5}`, `{-3..3}`,
 * including mixed-case letter walks) only ever produce single letters, digits,
 * or `-`, which can never traverse, so they are treated as literal here —
 * the runtime expansion is safe whenever the literal segment is.
 * Everything else bash keeps literal, so treating it as literal is exact.
 */
function expandBraceContent(content: string): BraceContentResult {
  const parts: string[] = [];
  let depth = 0;
  let start = 0;
  let hasTopLevelComma = false;

  for (let index = 0; index < content.length; index += 1) {
    const character = content[index];
    if (character === "\\") {
      index += 1;
      continue;
    }
    if (character === "{") {
      depth += 1;
      continue;
    }
    if (character === "}") {
      if (depth === 0) return { kind: "error" };
      depth -= 1;
      continue;
    }
    if (character === "," && depth === 0) {
      hasTopLevelComma = true;
      parts.push(content.slice(start, index));
      start = index + 1;
    }
  }

  if (depth !== 0) return { kind: "error" };
  if (!hasTopLevelComma) return { kind: "literal" };

  parts.push(content.slice(start));
  if (parts.some((part) => part.length === 0)) return { kind: "error" };
  return { kind: "alternatives", alternatives: parts };
}

/**
 * Returns every string the path can expand to through brace expansion, or
 * null when the expansion cannot be statically enumerated. A result of [path]
 * means the braces are literal text (or a safe range) and nothing is expanded.
 */
function braceExpand(path: string, depth = 0): string[] | null {
  if (depth > maxBraceDepth) return null;

  const open = findUnescapedOpenBrace(path);
  if (open === -1) return [path];
  const close = findMatchingCloseBrace(path, open);
  if (close === -1) return [path]; // unbalanced: bash keeps it literal

  const expansion = expandBraceContent(path.slice(open + 1, close));
  if (expansion.kind === "error") return null;
  if (expansion.kind === "literal") return [path];

  const before = path.slice(0, open);
  const after = path.slice(close + 1);
  const results: string[] = [];
  for (const alternative of expansion.alternatives) {
    const nested = braceExpand(`${before}${alternative}${after}`, depth + 1);
    if (nested === null) return null;
    results.push(...nested);
    if (results.length > maxBraceExpansions) return null;
  }
  return results;
}

/**
 * A lexically canonical descendant of /tmp/: starts with /tmp/, may end in a
 * single trailing slash (`rm -rf /tmp/foo/`), and has no empty, ".", or ".."
 * path segments. Shell patterns are permitted in segments; they can never
 * expand to ".", "..", or "/" at runtime.
 */
function isCanonicalTemporaryDirectoryEntry(path: string): boolean {
  if (!path.startsWith("/tmp/")) return false;

  const withoutTrailingSlash = path.endsWith("/") ? path.slice(0, -1) : path;
  if (withoutTrailingSlash === "/tmp") return false;

  const relativeSegments = withoutTrailingSlash.slice("/tmp/".length).split("/");
  return relativeSegments.length > 0 && relativeSegments.every((segment) => (
    segment.length > 0 && segment !== "." && segment !== ".."
  ));
}

function isTemporaryDirectoryEntry(path: string): boolean {
  const expansions = braceExpand(path);
  if (expansions === null) return false;
  return expansions.every(isCanonicalTemporaryDirectoryEntry);
}

/**
 * Permits only a single direct rm, rmdir, or unlink command whose literal operands
 * are lexically canonical descendants of /tmp/, allowing glob patterns, brace
 * expansions, and a trailing slash. Ambiguous commands continue to require
 * confirmation through the normal assessment path.
 */
export function isDirectTemporaryDirectoryDeletion(source: string): boolean {
  let script: ParsedScript;
  try {
    script = parse(source) as ParsedScript;
  } catch {
    return false;
  }

  if ((script.errors?.length ?? 0) > 0 || script.commands.length !== 1) return false;

  const statement = script.commands[0];
  if (statement === undefined || statement.background || statement.redirects.length > 0) return false;

  const command = statement.command;
  if (
    command.type !== "Command"
    || command.name === undefined
    || command.prefix.length > 0
    || command.redirects.length > 0
  ) return false;

  const commandName = literalWordValue(command.name);
  if (commandName === undefined || !directDeletionCommands.has(basename(commandName))) return false;

  const operands = directDeletionOperands(command.suffix);
  return operands !== undefined && operands.length > 0 && operands.every(isTemporaryDirectoryEntry);
}
