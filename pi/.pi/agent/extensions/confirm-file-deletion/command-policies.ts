import type { Word, WordPart } from "unbash";

import type { AssessmentFinding } from "./assessment.ts";

export type PolicyDecision =
  | { kind: "no-match" | "safe" }
  | { kind: "deletion" | "unknown"; policy: string; message: string };

export type PolicyContext = {
  assessCommandText: (source: string, span?: { start: number; end: number }) => void;
  assessNestedInvocation: (words: Word[]) => void;
};

const directDeletionCommands = new Set(["rm", "rmdir", "unlink"]);
const shellInterpreters = new Set(["bash", "sh", "dash", "ksh", "mksh", "zsh"]);
const wrappers = new Set(["command", "sudo", "doas", "exec", "nice", "nohup", "setsid", "time", "timeout"]);

export function basename(command: string): string {
  return command.split("/").at(-1) ?? command;
}

export function literalWordValue(word: Word | undefined): string | undefined {
  if (word === undefined) return undefined;
  if (word.parts === undefined) return word.value;

  return literalPartsValue(word.parts);
}

function literalPartsValue(parts: readonly WordPart[]): string | undefined {
  let value = "";

  for (const part of parts) {
    if (part.type === "Literal" || part.type === "SingleQuoted" || part.type === "AnsiCQuoted") {
      value += part.value;
      continue;
    }
    if (part.type === "DoubleQuoted" || part.type === "LocaleString") {
      const childValue = literalPartsValue(part.parts);
      if (childValue === undefined) return undefined;
      value += childValue;
      continue;
    }
    return undefined;
  }

  return value;
}

export function simpleParameterName(word: Word): string | undefined {
  const parts = word.parts;
  if (parts === undefined) return undefined;

  const expansion = parts.length === 1 && parts[0]?.type === "DoubleQuoted"
    ? parts[0].parts
    : parts;
  if (expansion.length !== 1) return undefined;

  const part = expansion[0];
  if (part?.type === "SimpleExpansion") {
    const match = /^\$([A-Za-z_][A-Za-z0-9_]*)$/.exec(part.text);
    return match?.[1];
  }
  if (part?.type === "ParameterExpansion" && part.operator === undefined && part.index === undefined) {
    return part.parameter;
  }
  return undefined;
}

function decision(kind: "deletion" | "unknown", policy: string, message: string): PolicyDecision {
  return { kind, policy, message };
}

function hasInformationalOption(argumentsList: Word[]): boolean {
  return argumentsList.some((word) => {
    const value = literalWordValue(word);
    return value === "--help" || value === "--version" || value === "-V";
  });
}

function hasDryRunOption(argumentsList: Word[]): boolean {
  return argumentsList.some((word) => {
    const value = literalWordValue(word);
    return value === "-n" || value === "--dry-run" || value?.startsWith("--dry-run=") === true;
  });
}

function directDeletionDecision(command: string, argumentsList: Word[]): PolicyDecision {
  if (hasInformationalOption(argumentsList)) return { kind: "safe" };

  let optionsEnded = false;
  for (const word of argumentsList) {
    const value = literalWordValue(word);
    if (!optionsEnded && value === "--") {
      optionsEnded = true;
      continue;
    }
    if (!optionsEnded && value !== undefined && value.startsWith("-") && value !== "-") continue;

    return decision("deletion", `direct-${command}`, `Direct ${command} invocation may delete file operands`);
  }

  return { kind: "safe" };
}

function consumeOption(
  argumentsList: Word[],
  index: number,
  optionsWithValues: ReadonlySet<string>,
): { nextIndex: number } | { error: true } {
  const value = literalWordValue(argumentsList[index]);
  if (value === undefined) return { error: true };
  if (value === "--") return { nextIndex: index + 1 };
  if (!value.startsWith("-") || value === "-") return { nextIndex: index };

  const equalsIndex = value.indexOf("=");
  const option = equalsIndex === -1 ? value : value.slice(0, equalsIndex);
  if (!optionsWithValues.has(option)) return { nextIndex: index + 1 };
  if (equalsIndex !== -1) return { nextIndex: index + 1 };
  if (argumentsList[index + 1] === undefined) return { error: true };
  return { nextIndex: index + 2 };
}

function skipWrapperOptions(
  argumentsList: Word[],
  optionsWithValues: ReadonlySet<string>,
  policy: string,
  optionsWithoutValues: ReadonlySet<string> = new Set(),
): { words: Word[] } | PolicyDecision {
  let index = 0;
  while (index < argumentsList.length) {
    const value = literalWordValue(argumentsList[index]);
    if (value === undefined) return decision("unknown", policy, "Wrapper options cannot be resolved statically");
    if (value === "--") return { words: argumentsList.slice(index + 1) };
    if (!value.startsWith("-") || value === "-") return { words: argumentsList.slice(index) };
    if (value === "--help" || value === "--version" || value === "-V") return { words: [] };

    const option = value.includes("=") ? value.slice(0, value.indexOf("=")) : value;
    if (!optionsWithValues.has(option) && !optionsWithoutValues.has(option)) {
      return decision("unknown", policy, `Unsupported wrapper option ${value} makes command dispatch ambiguous`);
    }
    const consumed = consumeOption(argumentsList, index, optionsWithValues);
    if ("error" in consumed) return decision("unknown", policy, "A wrapper option is missing its required value");
    index = consumed.nextIndex;
  }
  return { words: [] };
}

function wrapperDecision(command: string, argumentsList: Word[], context: PolicyContext): PolicyDecision {
  if (hasInformationalOption(argumentsList)) return { kind: "safe" };

  if (command === "timeout") {
    const skipped = skipWrapperOptions(
      argumentsList,
      new Set(["-k", "--kill-after", "-s", "--signal"]),
      "timeout-options",
    );
    if ("kind" in skipped) return skipped;
    if (skipped.words.length === 0) {
      return decision("unknown", "timeout-options", "timeout requires a duration and command");
    }
    const duration = literalWordValue(skipped.words[0]);
    if (duration === undefined || duration.startsWith("-")) {
      return decision("unknown", "timeout-options", "timeout duration cannot be identified safely");
    }
    if (skipped.words.length === 1) {
      return decision("unknown", "timeout-options", "timeout requires a command after its duration");
    }
    context.assessNestedInvocation(skipped.words.slice(1));
    return { kind: "safe" };
  }

  const optionsWithValues = command === "sudo" || command === "doas"
    ? new Set(["-C", "-g", "-h", "-p", "-r", "-t", "-u", "--chdir", "--group", "--host", "--prompt", "--role", "--user"])
    : command === "exec"
      ? new Set(["-a", "--argv0"])
      : command === "nice"
        ? new Set(["-n", "--adjustment"])
        : command === "time"
          ? new Set(["-f", "-o", "--format", "--output"])
          : new Set<string>();
  const optionsWithoutValues = command === "sudo"
    ? new Set(["-A", "-b", "-E", "-H", "-K", "-k", "-l", "-n", "-S", "-s", "-v", "--askpass", "--background", "--bell", "--edit", "--list", "--non-interactive", "--preserve-env", "--reset-timestamp", "--shell", "--stdin", "--validate"])
    : command === "doas"
      ? new Set(["-L", "-n", "-s"])
      : command === "exec"
        ? new Set(["-c", "-l"])
        : command === "time"
          ? new Set(["-a", "-p", "-v"])
          : command === "command"
            ? new Set(["-p", "-v", "-V"])
            : command === "setsid"
              ? new Set(["-c", "-f", "-w"])
              : new Set<string>();
  const skipped = skipWrapperOptions(argumentsList, optionsWithValues, "wrapper-options", optionsWithoutValues);
  if ("kind" in skipped) return skipped;

  if (command === "command") {
    const first = literalWordValue(argumentsList[0]);
    if (first === "-v" || first === "-V") return { kind: "safe" };
  }
  if (skipped.words.length > 0) context.assessNestedInvocation(skipped.words);
  return { kind: "safe" };
}

function environmentDecision(argumentsList: Word[], context: PolicyContext): PolicyDecision {
  if (hasInformationalOption(argumentsList)) return { kind: "safe" };

  let index = 0;
  while (index < argumentsList.length) {
    const word = argumentsList[index];
    const value = literalWordValue(word);
    if (value === undefined) return decision("unknown", "env-options", "env options cannot be resolved statically");
    if (value === "--") {
      index += 1;
      break;
    }
    if (!value.startsWith("-") || value === "-") break;
    if (value === "-i" || value === "--ignore-environment" || value === "-0" || value === "--null") {
      index += 1;
      continue;
    }
    if (value === "-S" || value === "--split-string") {
      const commandText = literalWordValue(argumentsList[index + 1]);
      if (commandText === undefined) {
        return decision("unknown", "env-options", "env split-string requires literal command text");
      }
      context.assessCommandText(commandText);
      return { kind: "safe" };
    }
    if (value.startsWith("-S") && value.length > 2) {
      context.assessCommandText(value.slice(2));
      return { kind: "safe" };
    }
    if (value.startsWith("--split-string=")) {
      context.assessCommandText(value.slice("--split-string=".length));
      return { kind: "safe" };
    }
    if (["-C", "-u", "--chdir", "--unset"].includes(value)) {
      if (argumentsList[index + 1] === undefined) {
        return decision("unknown", "env-options", `env option ${value} requires a value`);
      }
      index += 2;
      continue;
    }
    return decision("unknown", "env-options", `Unsupported env option ${value} makes command dispatch ambiguous`);
  }

  while (index < argumentsList.length) {
    const value = literalWordValue(argumentsList[index]);
    if (value === undefined || !/^[A-Za-z_][A-Za-z0-9_]*=/.test(value)) break;
    index += 1;
  }
  if (index < argumentsList.length) context.assessNestedInvocation(argumentsList.slice(index));
  return { kind: "safe" };
}

function dispatcherDecision(argumentsList: Word[], context: PolicyContext): PolicyDecision {
  if (hasInformationalOption(argumentsList)) return { kind: "safe" };
  const skipped = skipWrapperOptions(argumentsList, new Set(["--install"]), "dispatcher-options");
  if ("kind" in skipped) return skipped;
  if (skipped.words.length > 0) context.assessNestedInvocation(skipped.words);
  return { kind: "safe" };
}

function xargsDecision(argumentsList: Word[], context: PolicyContext): PolicyDecision {
  if (hasInformationalOption(argumentsList)) return { kind: "safe" };

  let index = 0;
  while (index < argumentsList.length) {
    const value = literalWordValue(argumentsList[index]);
    if (value === undefined) return decision("unknown", "xargs-options", "xargs options cannot be resolved statically");
    if (value === "--") {
      index += 1;
      break;
    }
    if (!value.startsWith("-") || value === "-") break;

    const longWithValue = new Set([
      "--arg-file", "--delimiter", "--eof", "--max-args", "--max-chars", "--max-lines", "--max-procs", "--replace",
    ]);
    const equalsIndex = value.indexOf("=");
    const option = equalsIndex === -1 ? value : value.slice(0, equalsIndex);
    if (longWithValue.has(option)) {
      if (equalsIndex === -1 && argumentsList[index + 1] === undefined) {
        return decision("unknown", "xargs-options", `${option} requires a value`);
      }
      index += equalsIndex === -1 ? 2 : 1;
      continue;
    }
    if (value.startsWith("--")) return decision("unknown", "xargs-options", `Unsupported xargs option ${value}`);

    const cluster = value.slice(1);
    const valueIndex = [...cluster].findIndex((character) => "adEILnPs".includes(character));
    if (valueIndex === -1) {
      if (![...cluster].every((character) => "0prt x".replaceAll(" ", "").includes(character))) {
        return decision("unknown", "xargs-options", `Unsupported xargs option ${value}`);
      }
      index += 1;
      continue;
    }
    if (valueIndex + 1 < cluster.length) {
      index += 1;
      continue;
    }
    if (argumentsList[index + 1] === undefined) return decision("unknown", "xargs-options", `${value} requires a value`);
    index += 2;
  }

  const dispatchedWords = argumentsList.slice(index);
  const dispatchedName = literalWordValue(dispatchedWords[0]);
  if (dispatchedName !== undefined && directDeletionCommands.has(basename(dispatchedName))) {
    context.assessNestedInvocation(dispatchedWords);
    return decision("deletion", "xargs-dispatch", "xargs may dispatch a file-deletion command for standard input");
  }
  if (dispatchedWords.length > 0) context.assessNestedInvocation(dispatchedWords);
  return { kind: "safe" };
}

function findDecision(argumentsList: Word[], context: PolicyContext): PolicyDecision {
  const predicatesWithOneArgument = new Set([
    "-amin", "-anewer", "-atime", "-cmin", "-cnewer", "-ctime", "-fstype", "-gid", "-group", "-ilname", "-iname", "-ipath", "-iregex", "-iwholename", "-links", "-lname", "-mmin", "-mtime", "-name", "-newer", "-newerXY", "-path", "-perm", "-printf", "-regex", "-samefile", "-size", "-type", "-uid", "-user", "-wholename", "-xtype",
  ]);
  for (let index = 0; index < argumentsList.length; index += 1) {
    const value = literalWordValue(argumentsList[index]);
    if (value === "-delete") return decision("deletion", "find-delete", "find -delete may remove matching files");
    if (value === "-fprintf") {
      index += 2;
      continue;
    }
    if (predicatesWithOneArgument.has(value ?? "")) {
      index += 1;
      continue;
    }
    if (!["-exec", "-execdir", "-ok", "-okdir"].includes(value ?? "")) continue;

    let endIndex = index + 1;
    while (endIndex < argumentsList.length) {
      const candidate = literalWordValue(argumentsList[endIndex]);
      if (candidate === ";" || candidate === "+") break;
      endIndex += 1;
    }
    if (endIndex === argumentsList.length || endIndex === index + 1) {
      return decision("unknown", "find-exec", "find execution action is incomplete");
    }
    context.assessNestedInvocation(argumentsList.slice(index + 1, endIndex));
    index = endIndex;
  }
  return { kind: "safe" };
}

function gitDecision(argumentsList: Word[]): PolicyDecision {
  if (hasInformationalOption(argumentsList)) return { kind: "safe" };

  let index = 0;
  const optionsWithValues = new Set(["-C", "-c", "--config-env", "--exec-path", "--git-dir", "--namespace", "--super-prefix", "--work-tree"]);
  while (index < argumentsList.length) {
    const value = literalWordValue(argumentsList[index]);
    if (value === undefined) return decision("unknown", "git-options", "git options cannot be resolved statically");
    if (value === "--") return { kind: "safe" };
    if (!value.startsWith("-") || value === "-") break;
    const consumed = consumeOption(argumentsList, index, optionsWithValues);
    if ("error" in consumed) return decision("unknown", "git-options", "git option is missing its value");
    index = consumed.nextIndex;
  }

  const subcommand = literalWordValue(argumentsList[index]);
  const subcommandArguments = argumentsList.slice(index + 1);
  if (subcommand === "clean") {
    return hasDryRunOption(subcommandArguments)
      ? { kind: "safe" }
      : decision("deletion", "git-clean", "git clean may remove untracked files");
  }
  if (subcommand === "rm") {
    if (hasDryRunOption(subcommandArguments) || subcommandArguments.some((word) => literalWordValue(word) === "--cached")) {
      return { kind: "safe" };
    }
    const hasPathspecFile = subcommandArguments.some((word) => literalWordValue(word)?.startsWith("--pathspec-from-file=") === true)
      || subcommandArguments.some((word, argumentIndex) => literalWordValue(word) === "--pathspec-from-file" && subcommandArguments[argumentIndex + 1] !== undefined);
    const hasOperand = subcommandArguments.some((word) => {
      const value = literalWordValue(word);
      return value !== "--" && (value === undefined || !value.startsWith("-"));
    });
    return hasOperand || hasPathspecFile
      ? decision("deletion", "git-rm", "git rm may remove tracked files")
      : { kind: "safe" };
  }
  return { kind: "safe" };
}

function shredDecision(argumentsList: Word[]): PolicyDecision {
  if (hasInformationalOption(argumentsList)) return { kind: "safe" };
  let remove = false;
  let hasOperand = false;
  let optionsEnded = false;
  for (const word of argumentsList) {
    const value = literalWordValue(word);
    if (!optionsEnded && value === "--") {
      optionsEnded = true;
      continue;
    }
    if (!optionsEnded && value !== undefined && value.startsWith("-") && value !== "-") {
      if (value === "-u" || value.startsWith("--remove") || (/^-[A-Za-z]+$/.test(value) && value.includes("u"))) remove = true;
      continue;
    }
    hasOperand = true;
  }
  return remove && hasOperand
    ? decision("deletion", "shred-remove", "shred --remove may delete files")
    : { kind: "safe" };
}

function rsyncDecision(argumentsList: Word[]): PolicyDecision {
  if (hasInformationalOption(argumentsList) || hasDryRunOption(argumentsList)) return { kind: "safe" };
  if (argumentsList.some((word) => literalWordValue(word)?.startsWith("--delete") === true)) {
    return decision("deletion", "rsync-delete", "rsync --delete may remove destination files");
  }
  if (argumentsList.some((word) => literalWordValue(word) === "--remove-source-files")) {
    return decision("deletion", "rsync-remove-source-files", "rsync may remove source files after transfer");
  }
  return { kind: "safe" };
}

function interpreterDecision(command: string, argumentsList: Word[], context: PolicyContext): PolicyDecision {
  if (command === "eval") {
    const words = argumentsList.map(literalWordValue);
    if (words.some((word) => word === undefined)) {
      return decision("unknown", "eval-command-string", "eval command text cannot be resolved statically");
    }
    if (words.length > 0) context.assessCommandText(words.join(" "));
    return { kind: "safe" };
  }

  let commandText: string | undefined;
  for (let index = 0; index < argumentsList.length; index += 1) {
    const value = literalWordValue(argumentsList[index]);
    if (value === undefined) return decision("unknown", "interpreter-options", "Interpreter options cannot be resolved statically");
    if (value === "--") break;
    if (!value.startsWith("-") || value === "-") break;
    if (value.startsWith("--command=")) {
      commandText = value.slice("--command=".length);
      break;
    }
    if (value === "-c" || value === "--command" || /^-[^-]*c/.test(value)) {
      const commandIndex = literalWordValue(argumentsList[index + 1]) === "--" ? index + 2 : index + 1;
      commandText = literalWordValue(argumentsList[commandIndex]);
      if (commandText === undefined) {
        return decision("unknown", "interpreter-options", "Interpreter -c requires literal command text");
      }
      break;
    }
    if (["-O", "-o", "--init-file", "--rcfile"].includes(value)) {
      if (argumentsList[index + 1] === undefined) {
        return decision("unknown", "interpreter-options", `${value} requires a value`);
      }
      index += 1;
      continue;
    }
    if (value.startsWith("--") && !["--noprofile", "--norc", "--posix", "--restricted", "--verbose", "--debugger"].includes(value)) {
      return decision("unknown", "interpreter-options", `Unsupported interpreter option ${value}`);
    }
  }

  if (commandText !== undefined) context.assessCommandText(commandText);
  return { kind: "safe" };
}

export function assessCommandPolicy(commandName: string, argumentsList: Word[], context: PolicyContext): PolicyDecision {
  const command = basename(commandName);
  if (directDeletionCommands.has(command)) return directDeletionDecision(command, argumentsList);
  if (wrappers.has(command)) return wrapperDecision(command, argumentsList, context);
  if (command === "env") return environmentDecision(argumentsList, context);
  if (command === "busybox" || command === "toybox") return dispatcherDecision(argumentsList, context);
  if (command === "xargs") return xargsDecision(argumentsList, context);
  if (command === "find") return findDecision(argumentsList, context);
  if (command === "git") return gitDecision(argumentsList);
  if (command === "shred") return shredDecision(argumentsList);
  if (command === "rsync") return rsyncDecision(argumentsList);
  if (command === "eval" || shellInterpreters.has(command)) return interpreterDecision(command, argumentsList, context);
  if (command === "fish") {
    return argumentsList.some((word) => {
      const value = literalWordValue(word);
      return value === "-c" || value === "--command" || value?.startsWith("--command=") === true;
    })
      ? decision("unknown", "unsupported-interpreter", "fish command strings are not parsed as Bash")
      : { kind: "safe" };
  }
  return { kind: "no-match" };
}

export function policyFinding(
  policyDecision: Exclude<PolicyDecision, { kind: "no-match" | "safe" }>,
  span?: { start: number; end: number },
): AssessmentFinding {
  return { ...policyDecision, span };
}
