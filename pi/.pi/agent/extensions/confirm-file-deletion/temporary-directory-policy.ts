import { parse, type Script, type Word } from "unbash";

import { basename, literalWordValue } from "./command-policies.ts";

const directDeletionCommands = new Set(["rm", "rmdir", "unlink"]);
const shellPatternCharacters = /[*!?\[\]{}()]/;

type ParsedScript = Script & { errors?: Array<unknown> };

function directDeletionOperands(argumentsList: Word[]): string[] | undefined {
  let optionsEnded = false;
  const operands: string[] = [];

  for (const word of argumentsList) {
    const value = literalWordValue(word);
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

function isTemporaryDirectoryEntry(path: string): boolean {
  if (!path.startsWith("/tmp/")) return false;

  const relativeSegments = path.slice("/tmp/".length).split("/");
  return relativeSegments.every((segment) => (
    segment.length > 0
    && segment !== "."
    && segment !== ".."
    && !shellPatternCharacters.test(segment)
  ));
}

/**
 * Permits only a single direct rm, rmdir, or unlink command whose literal operands
 * are lexically canonical descendants of /tmp/. Ambiguous commands continue to require
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
