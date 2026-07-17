import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

type ShellToken =
  | { type: "word"; value: string }
  | { type: "operator" };

type ShellInvocation = {
  command: string;
  arguments: ShellToken[];
};

const directDeletionCommands = new Set(["rm", "rmdir", "unlink"]);
const commandDispatchers = new Set(["busybox", "toybox"]);
const shellWrappers = new Set(["command", "doas", "exec", "nice", "nohup", "setsid", "sudo", "time"]);
const shellInterpreters = new Set(["bash", "dash", "fish", "ksh", "sh", "zsh"]);
const shellKeywords = new Set(["!", "case", "do", "done", "elif", "else", "esac", "fi", "for", "if", "in", "select", "then", "until", "while"]);
const dynamicCommandMarker = "__dynamic_command__";
const rpcConfirmationTimeoutMs = 30_000;

function commandName(command: string): string {
  const pathParts = command.split("/");
  return pathParts.at(-1) ?? command;
}

function isEnvironmentAssignment(token: ShellToken): boolean {
  return token.type === "word" && /^[A-Za-z_][A-Za-z0-9_]*=/.test(token.value);
}

function commandSubstitutionEnd(command: string, startIndex: number): number | undefined {
  let depth = 1;
  let quote: "'" | '"' | "`" | undefined;

  for (let index = startIndex; index < command.length; index += 1) {
    const character = command[index];

    if (quote !== undefined) {
      if (character === "\\" && quote !== "'" && index + 1 < command.length) {
        index += 1;
      } else if (character === quote) {
        quote = undefined;
      }
      continue;
    }

    if (character === "'" || character === '"' || character === "`") {
      quote = character;
    } else if (character === "\\" && index + 1 < command.length) {
      index += 1;
    } else if (character === "(") {
      depth += 1;
    } else if (character === ")") {
      depth -= 1;
      if (depth === 0) return index;
    }
  }

  return undefined;
}

function arithmeticExpansionEnd(command: string, startIndex: number): number | undefined {
  let depth = 1;
  let quote: "'" | '"' | "`" | undefined;

  for (let index = startIndex; index < command.length; index += 1) {
    const character = command[index];

    if (quote !== undefined) {
      if (character === "\\" && quote !== "'" && index + 1 < command.length) {
        index += 1;
      } else if (character === quote) {
        quote = undefined;
      }
      continue;
    }

    if (character === "'" || character === '"' || character === "`") {
      quote = character;
    } else if (character === "\\" && index + 1 < command.length) {
      index += 1;
    } else if (character === "(") {
      depth += 1;
    } else if (character === ")") {
      depth -= 1;
      if (depth === 0 && command[index + 1] === ")") return index + 1;
    }
  }

  return undefined;
}

function backtickSubstitutionEnd(command: string, startIndex: number): number | undefined {
  for (let index = startIndex; index < command.length; index += 1) {
    if (command[index] === "\\" && index + 1 < command.length) {
      index += 1;
    } else if (command[index] === "`") {
      return index;
    }
  }

  return undefined;
}

type HereDocumentDelimiter = {
  value: string;
  stripLeadingTabs: boolean;
};

function stripShellComment(line: string): string {
  let quote: "'" | '"' | "`" | undefined;
  let startsWord = true;

  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];

    if (quote !== undefined) {
      if (character === "\\" && quote !== "'" && index + 1 < line.length) {
        index += 1;
      } else if (character === quote) {
        quote = undefined;
      }
      continue;
    }

    if (character === "'" || character === '"' || character === "`") {
      quote = character;
      startsWord = false;
    } else if (character === "\\" && index + 1 < line.length) {
      index += 1;
      startsWord = false;
    } else if (character === "#" && startsWord) {
      return line.slice(0, index);
    } else if (/\s/.test(character) || ";&|(){}".includes(character)) {
      startsWord = true;
    } else {
      startsWord = false;
    }
  }

  return line;
}

function hereDocumentDelimiters(line: string): HereDocumentDelimiter[] {
  const delimiters: HereDocumentDelimiter[] = [];
  let quote: "'" | '"' | undefined;

  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];

    if (quote !== undefined) {
      if (character === "\\" && quote === '"' && index + 1 < line.length) {
        index += 1;
      } else if (character === quote) {
        quote = undefined;
      }
      continue;
    }

    if (character === "'" || character === '"') {
      quote = character;
      continue;
    }
    if (character === "\\" && index + 1 < line.length) {
      index += 1;
      continue;
    }
    if (character !== "<" || line[index + 1] !== "<" || line[index + 2] === "<") continue;

    let delimiterIndex = index + 2;
    const stripLeadingTabs = line[delimiterIndex] === "-";
    if (stripLeadingTabs) delimiterIndex += 1;
    while (/\s/.test(line[delimiterIndex] ?? "")) delimiterIndex += 1;

    let delimiter = "";
    let delimiterQuote: "'" | '"' | undefined;
    for (; delimiterIndex < line.length; delimiterIndex += 1) {
      const delimiterCharacter = line[delimiterIndex];
      if (delimiterQuote !== undefined) {
        if (delimiterCharacter === "\\" && delimiterQuote === '"' && delimiterIndex + 1 < line.length) {
          delimiterIndex += 1;
          delimiter += line[delimiterIndex];
        } else if (delimiterCharacter === delimiterQuote) {
          delimiterQuote = undefined;
        } else {
          delimiter += delimiterCharacter;
        }
        continue;
      }
      if (delimiterCharacter === "'" || delimiterCharacter === '"') {
        delimiterQuote = delimiterCharacter;
      } else if (delimiterCharacter === "\\" && delimiterIndex + 1 < line.length) {
        delimiterIndex += 1;
        delimiter += line[delimiterIndex];
      } else if (/\s/.test(delimiterCharacter) || ";&|(){}<>".includes(delimiterCharacter)) {
        break;
      } else {
        delimiter += delimiterCharacter;
      }
    }

    if (delimiter.length > 0) {
      delimiters.push({ value: delimiter, stripLeadingTabs });
      index = delimiterIndex - 1;
    }
  }

  return delimiters;
}

function executableShellSource(command: string): string {
  const sourceLines: string[] = [];
  const pendingHereDocuments: HereDocumentDelimiter[] = [];

  for (const originalLine of command.split("\n")) {
    const pendingHereDocument = pendingHereDocuments[0];
    if (pendingHereDocument !== undefined) {
      const comparisonLine = pendingHereDocument.stripLeadingTabs
        ? originalLine.replace(/^\t+/, "")
        : originalLine;
      if (comparisonLine === pendingHereDocument.value) pendingHereDocuments.shift();
      sourceLines.push("");
      continue;
    }

    const line = stripShellComment(originalLine);
    sourceLines.push(line);
    pendingHereDocuments.push(...hereDocumentDelimiters(line));
  }

  return sourceLines.join("\n");
}

function tokenize(command: string): ShellToken[] {
  const tokens: ShellToken[] = [];
  let currentWord = "";
  let currentWordStarted = false;
  let quote: "'" | '"' | undefined;

  const pushCurrentWord = () => {
    if (!currentWordStarted) return;
    tokens.push({ type: "word", value: currentWord });
    currentWord = "";
    currentWordStarted = false;
  };

  const pushOperator = () => {
    if (tokens.at(-1)?.type !== "operator") {
      tokens.push({ type: "operator" });
    }
  };

  for (let index = 0; index < command.length; index += 1) {
    const character = command[index];

    if (quote !== undefined) {
      if (character === quote) {
        quote = undefined;
      } else if (character === "\\" && quote === '"' && index + 1 < command.length) {
        if (command[index + 1] !== "\n") currentWord += command[index + 1];
        index += 1;
      } else {
        currentWord += character;
      }
      continue;
    }

    if (character === "'" || character === '"') {
      quote = character;
      currentWordStarted = true;
      continue;
    }

    if (character === "\\" && index + 1 < command.length) {
      if (command[index + 1] !== "\n") {
        currentWord += command[index + 1];
        currentWordStarted = true;
      }
      index += 1;
      continue;
    }

    if (character === "#" && !currentWordStarted) {
      while (index + 1 < command.length && command[index + 1] !== "\n") {
        index += 1;
      }
      continue;
    }

    if (character === "$" && command[index + 1] === "(") {
      const endIndex = commandSubstitutionEnd(command, index + 2);
      if (endIndex !== undefined) {
        currentWord += command.slice(index, endIndex + 1);
        currentWordStarted = true;
        index = endIndex;
        continue;
      }
    }

    if (character === "`") {
      const endIndex = backtickSubstitutionEnd(command, index + 1);
      if (endIndex !== undefined) {
        currentWord += command.slice(index, endIndex + 1);
        currentWordStarted = true;
        index = endIndex;
        continue;
      }
    }

    if (/\s/.test(character)) {
      pushCurrentWord();
      if (character === "\n") pushOperator();
      continue;
    }

    if (character === "{" && command[index + 1] === "}") {
      currentWord += "{}";
      currentWordStarted = true;
      index += 1;
      continue;
    }

    if (";&|(){}".includes(character)) {
      pushCurrentWord();
      pushOperator();
      if ((character === "&" || character === "|") && command[index + 1] === character) {
        index += 1;
      }
      continue;
    }

    currentWord += character;
    currentWordStarted = true;
  }

  pushCurrentWord();
  return tokens;
}

function shellSegments(tokens: ShellToken[]): ShellToken[][] {
  const segments: ShellToken[][] = [];
  let currentSegment: ShellToken[] = [];

  for (const token of tokens) {
    if (token.type === "operator") {
      if (currentSegment.length > 0) {
        segments.push(currentSegment);
        currentSegment = [];
      }
      continue;
    }
    currentSegment.push(token);
  }

  if (currentSegment.length > 0) {
    segments.push(currentSegment);
  }

  return segments;
}

function skipOptions(tokens: ShellToken[], startIndex: number, optionsWithArguments: Set<string>): number {
  let index = startIndex;

  while (index < tokens.length) {
    const token = tokens[index];
    if (token.type !== "word" || !token.value.startsWith("-")) break;

    if (token.value === "--") return index + 1;

    const option = token.value;
    index += 1;
    if (optionsWithArguments.has(option) && index < tokens.length) {
      index += 1;
    }
  }

  return index;
}

function environmentExecutesDeletion(argumentsList: ShellToken[]): boolean {
  if (hasInformationalOption(argumentsList)) return false;

  const optionArguments = new Set(["-C", "-S", "-u", "--chdir", "--split-string", "--unset"]);
  let index = 0;

  while (index < argumentsList.length) {
    const token = argumentsList[index];
    if (token?.type !== "word" || !token.value.startsWith("-")) break;

    if (token.value === "--") {
      index += 1;
      break;
    }
    if (token.value === "-S" || token.value === "--split-string") {
      const commandText = argumentsList[index + 1];
      return commandText?.type === "word" && isFileDeletionCommand(commandText.value);
    }
    if (token.value.startsWith("--split-string=")) {
      return isFileDeletionCommand(token.value.slice("--split-string=".length));
    }

    index += 1;
    if (optionArguments.has(token.value)) index += 1;
  }

  while (index < argumentsList.length && isEnvironmentAssignment(argumentsList[index])) {
    index += 1;
  }

  const invocation = invocationFrom(argumentsList.slice(index));
  return invocation !== undefined && invocationDeletesFiles(invocation);
}

function isDynamicCommandName(command: string): boolean {
  return command.includes("$") || command.includes("`");
}

function invocationFrom(tokens: ShellToken[]): ShellInvocation | undefined {
  let index = 0;

  while (index < tokens.length && isEnvironmentAssignment(tokens[index])) {
    index += 1;
  }

  while (index < tokens.length) {
    const token = tokens[index];
    if (token.type !== "word") return undefined;

    const name = commandName(token.value);
    if (shellKeywords.has(name)) {
      index += 1;
      continue;
    }
    if (isDynamicCommandName(name)) {
      return { command: dynamicCommandMarker, arguments: tokens.slice(index + 1) };
    }
    if (name === "command") {
      return { command: name, arguments: tokens.slice(index + 1) };
    }
    if (!shellWrappers.has(name)) {
      return { command: name, arguments: tokens.slice(index + 1) };
    }

    index += 1;
    if (name === "sudo" || name === "doas") {
      index = skipOptions(
        tokens,
        index,
        new Set([
          "-C",
          "-g",
          "-h",
          "-p",
          "-r",
          "-t",
          "-u",
          "--chdir",
          "--group",
          "--host",
          "--prompt",
          "--role",
          "--user",
        ]),
      );
    } else if (name === "exec") {
      index = skipOptions(tokens, index, new Set(["-a", "--argv0"]));
    } else if (name === "nice") {
      index = skipOptions(tokens, index, new Set(["-n", "--adjustment"]));
    } else if (name === "time") {
      index = skipOptions(tokens, index, new Set(["-f", "-o", "--format", "--output"]));
    } else {
      index = skipOptions(tokens, index, new Set());
    }
  }

  return undefined;
}

function commandExecutesDeletion(argumentsList: ShellToken[]): boolean {
  let index = 0;

  while (index < argumentsList.length) {
    const token = argumentsList[index];
    if (token?.type !== "word") return false;
    if (token.value === "--") {
      index += 1;
      break;
    }
    if (!token.value.startsWith("-") || token.value === "-") break;
    if (
      token.value === "--help" ||
      token.value === "--version" ||
      token.value === "-v" ||
      token.value === "-V" ||
      (/^-[^-]+$/.test(token.value) && (token.value.includes("v") || token.value.includes("V")))
    ) {
      return false;
    }
    index += 1;
  }

  const invocation = invocationFrom(argumentsList.slice(index));
  return invocation !== undefined && invocationDeletesFiles(invocation);
}

function skipDispatcherOptions(argumentsList: ShellToken[]): ShellToken[] {
  let index = 0;
  while (index < argumentsList.length) {
    const token = argumentsList[index];
    if (token?.type !== "word" || !token.value.startsWith("-")) break;
    if (token.value === "--") return argumentsList.slice(index + 1);
    index += token.value === "--install" ? 2 : 1;
  }
  return argumentsList.slice(index);
}

function dispatcherExecutesDeletion(argumentsList: ShellToken[]): boolean {
  if (hasInformationalOption(argumentsList)) return false;
  const invocation = invocationFrom(skipDispatcherOptions(argumentsList));
  return invocation !== undefined && invocationDeletesFiles(invocation);
}

function hasFileOperand(argumentsList: ShellToken[]): boolean {
  let optionsEnded = false;

  for (const token of argumentsList) {
    if (token.type !== "word") continue;
    if (!optionsEnded && token.value === "--") {
      optionsEnded = true;
      continue;
    }
    if (!optionsEnded && token.value.startsWith("-")) continue;
    return true;
  }

  return false;
}

function findActionEnd(argumentsList: ShellToken[], startIndex: number): number {
  for (let index = startIndex; index < argumentsList.length; index += 1) {
    const token = argumentsList[index];
    if (token.type === "word" && (token.value === ";" || token.value === "+")) return index;
  }
  return argumentsList.length;
}

function findExecutesDeletion(argumentsList: ShellToken[]): boolean {
  const expressionsWithOneArgument = new Set([
    "-amin",
    "-anewer",
    "-atime",
    "-cmin",
    "-cnewer",
    "-ctime",
    "-fstype",
    "-gid",
    "-group",
    "-ilname",
    "-iname",
    "-ipath",
    "-iregex",
    "-iwholename",
    "-links",
    "-lname",
    "-mmin",
    "-mtime",
    "-name",
    "-newer",
    "-newerXY",
    "-path",
    "-perm",
    "-printf",
    "-regex",
    "-samefile",
    "-size",
    "-type",
    "-uid",
    "-user",
    "-wholename",
    "-xtype",
  ]);
  const executionActions = new Set(["-exec", "-execdir", "-ok", "-okdir"]);

  for (let index = 0; index < argumentsList.length; index += 1) {
    const token = argumentsList[index];
    if (token.type !== "word") continue;

    if (token.value === "-delete") return true;
    if (token.value === "-fprintf") {
      index += 2;
      continue;
    }
    if (expressionsWithOneArgument.has(token.value)) {
      index += 1;
      continue;
    }
    if (!executionActions.has(token.value)) continue;

    const actionEnd = findActionEnd(argumentsList, index + 1);
    const invocation = invocationFrom(argumentsList.slice(index + 1, actionEnd));
    if (invocation !== undefined && invocationDeletesFiles(invocation)) return true;
    index = actionEnd;
  }

  return false;
}

function hasInformationalOption(argumentsList: ShellToken[]): boolean {
  let optionsEnded = false;

  for (const token of argumentsList) {
    if (token.type !== "word") continue;
    if (!optionsEnded && token.value === "--") {
      optionsEnded = true;
      continue;
    }
    if (!optionsEnded && (token.value === "--help" || token.value === "--version")) return true;
  }

  return false;
}

function xargsExecutesDeletion(argumentsList: ShellToken[]): boolean {
  const optionArguments = new Set([
    "-a",
    "-d",
    "-E",
    "-I",
    "-L",
    "-n",
    "-P",
    "-s",
    "--arg-file",
    "--delimiter",
    "--eof",
    "--max-args",
    "--max-chars",
    "--max-lines",
    "--max-procs",
    "--replace",
  ]);
  const commandIndex = skipOptions(argumentsList, 0, optionArguments);
  const invocation = invocationFrom(argumentsList.slice(commandIndex));
  if (invocation === undefined) return false;

  if (directDeletionCommands.has(invocation.command)) {
    return !hasInformationalOption(invocation.arguments);
  }

  return invocationDeletesFiles(invocation);
}

function containsOption(argumentsList: ShellToken[], option: string): boolean {
  let optionsEnded = false;

  for (const token of argumentsList) {
    if (token.type !== "word") continue;
    if (!optionsEnded && token.value === "--") {
      optionsEnded = true;
      continue;
    }
    if (optionsEnded) continue;

    if (token.value === option || token.value.startsWith(`${option}=`)) return true;
    if (
      option.length === 2 &&
      token.value.startsWith("-") &&
      !token.value.startsWith("--") &&
      token.value.slice(1).includes(option[1])
    ) {
      return true;
    }
  }

  return false;
}

function gitCleansFiles(argumentsList: ShellToken[]): boolean {
  if (hasInformationalOption(argumentsList)) return false;
  return !containsOption(argumentsList, "-n") && !containsOption(argumentsList, "--dry-run");
}

function hasOptionWithArgument(argumentsList: ShellToken[], option: string): boolean {
  for (let index = 0; index < argumentsList.length; index += 1) {
    const token = argumentsList[index];
    if (token?.type !== "word") continue;
    if (token.value.startsWith(`${option}=`)) return true;
    if (token.value === option && argumentsList[index + 1]?.type === "word") return true;
  }
  return false;
}

function gitRemovesFiles(argumentsList: ShellToken[]): boolean {
  if (hasInformationalOption(argumentsList)) return false;
  if (containsOption(argumentsList, "-n") || containsOption(argumentsList, "--dry-run")) return false;
  if (containsOption(argumentsList, "--cached")) return false;
  return hasFileOperand(argumentsList) || hasOptionWithArgument(argumentsList, "--pathspec-from-file");
}

function gitDeletesFiles(argumentsList: ShellToken[]): boolean {
  const optionArguments = new Set([
    "-C",
    "-c",
    "--config-env",
    "--exec-path",
    "--git-dir",
    "--namespace",
    "--super-prefix",
    "--work-tree",
  ]);
  const subcommandIndex = skipOptions(argumentsList, 0, optionArguments);
  const subcommand = argumentsList[subcommandIndex];
  if (subcommand?.type !== "word") return false;

  const subcommandArguments = argumentsList.slice(subcommandIndex + 1);
  if (subcommand.value === "clean") return gitCleansFiles(subcommandArguments);
  if (subcommand.value === "rm") return gitRemovesFiles(subcommandArguments);
  return false;
}

function shredRemovesFiles(argumentsList: ShellToken[]): boolean {
  if (hasInformationalOption(argumentsList)) return false;

  let optionsEnded = false;
  for (const token of argumentsList) {
    if (token.type !== "word") continue;
    if (!optionsEnded && token.value === "--") {
      optionsEnded = true;
      continue;
    }
    if (optionsEnded) continue;

    if (token.value === "-u" || token.value.startsWith("--remove")) return true;
    if (/^-[A-Za-z]+$/.test(token.value) && token.value.slice(1).includes("u")) return true;
  }

  return false;
}

function commandTextAfterInterpreterOption(argumentsList: ShellToken[], optionIndex: number): string | undefined {
  const commandToken = argumentsList[optionIndex + 1];
  if (commandToken?.type === "word" && commandToken.value === "--") {
    return argumentsList[optionIndex + 2]?.type === "word" ? argumentsList[optionIndex + 2].value : undefined;
  }
  return commandToken?.type === "word" ? commandToken.value : undefined;
}

function interpreterCommandText(argumentsList: ShellToken[]): string | undefined {
  const optionsWithArguments = new Set(["-O", "-o", "--init-file", "--rcfile"]);

  for (let index = 0; index < argumentsList.length; index += 1) {
    const token = argumentsList[index];
    if (token?.type !== "word") return undefined;
    if (token.value === "--") return undefined;
    if (!token.value.startsWith("-") || token.value === "-") return undefined;
    if (token.value.startsWith("--command=")) return token.value.slice("--command=".length);
    if (token.value === "--command" || token.value === "-c" || /^-[^-]*c/.test(token.value)) {
      return commandTextAfterInterpreterOption(argumentsList, index);
    }
    if (optionsWithArguments.has(token.value)) index += 1;
  }

  return undefined;
}

function interpreterExecutesDeletion(command: string, argumentsList: ShellToken[]): boolean {
  if (command === "eval") {
    return isFileDeletionCommand(
      argumentsList
        .filter((token): token is Extract<ShellToken, { type: "word" }> => token.type === "word")
        .map((token) => token.value)
        .join(" "),
    );
  }

  const commandText = interpreterCommandText(argumentsList);
  return commandText !== undefined && isFileDeletionCommand(commandText);
}

function invocationDeletesFiles(invocation: ShellInvocation): boolean {
  if (invocation.command === dynamicCommandMarker) return true;
  if (invocation.command === "command") return commandExecutesDeletion(invocation.arguments);
  if (commandDispatchers.has(invocation.command)) return dispatcherExecutesDeletion(invocation.arguments);
  if (invocation.command === "env") return environmentExecutesDeletion(invocation.arguments);
  if (directDeletionCommands.has(invocation.command)) {
    return !hasInformationalOption(invocation.arguments) && hasFileOperand(invocation.arguments);
  }
  if (invocation.command === "find") return findExecutesDeletion(invocation.arguments);
  if (invocation.command === "xargs") return xargsExecutesDeletion(invocation.arguments);
  if (invocation.command === "git") return gitDeletesFiles(invocation.arguments);
  if (invocation.command === "shred") return shredRemovesFiles(invocation.arguments);
  if (invocation.command === "eval" || shellInterpreters.has(invocation.command)) {
    return interpreterExecutesDeletion(invocation.command, invocation.arguments);
  }
  return false;
}

function commandSubstitutionsDeleteFiles(command: string): boolean {
  let quote: "'" | '"' | undefined;

  for (let index = 0; index < command.length; index += 1) {
    const character = command[index];

    if (quote !== undefined) {
      if (character === quote) {
        quote = undefined;
      } else if (character === "\\" && quote === '"' && index + 1 < command.length) {
        index += 1;
      } else if (quote === '"' && character === "$") {
        if (command[index + 1] !== "(") continue;

        if (command[index + 2] === "(") {
          const endIndex = arithmeticExpansionEnd(command, index + 3);
          if (endIndex !== undefined) {
            if (commandSubstitutionsDeleteFiles(command.slice(index + 3, endIndex - 1))) return true;
            index = endIndex;
          }
          continue;
        }

        const endIndex = commandSubstitutionEnd(command, index + 2);
        if (endIndex !== undefined) {
          if (isFileDeletionCommand(command.slice(index + 2, endIndex))) return true;
          index = endIndex;
        }
      } else if (quote === '"' && character === "`") {
        const endIndex = backtickSubstitutionEnd(command, index + 1);
        if (endIndex !== undefined) {
          if (isFileDeletionCommand(command.slice(index + 1, endIndex))) return true;
          index = endIndex;
        }
      }
      continue;
    }

    if (character === "'" || character === '"') {
      quote = character;
    } else if (character === "\\" && index + 1 < command.length) {
      index += 1;
    } else if (character === "$" && command[index + 1] === "(") {
      if (command[index + 2] === "(") {
        const endIndex = arithmeticExpansionEnd(command, index + 3);
        if (endIndex !== undefined) {
          if (commandSubstitutionsDeleteFiles(command.slice(index + 3, endIndex - 1))) return true;
          index = endIndex;
        }
        continue;
      }

      const endIndex = commandSubstitutionEnd(command, index + 2);
      if (endIndex !== undefined) {
        if (isFileDeletionCommand(command.slice(index + 2, endIndex))) return true;
        index = endIndex;
      }
    } else if (character === "`") {
      const endIndex = backtickSubstitutionEnd(command, index + 1);
      if (endIndex !== undefined) {
        if (isFileDeletionCommand(command.slice(index + 1, endIndex))) return true;
        index = endIndex;
      }
    }
  }

  return false;
}

export function isFileDeletionCommand(command: string): boolean {
  const executableSource = executableShellSource(command);
  if (commandSubstitutionsDeleteFiles(executableSource)) return true;

  return shellSegments(tokenize(executableSource)).some((segment) => {
    const invocation = invocationFrom(segment);
    return invocation !== undefined && invocationDeletesFiles(invocation);
  });
}

type ConfirmationOutcome = "approved" | "declined" | "unavailable" | "failed";

function confirmationBlockedReason(outcome: Exclude<ConfirmationOutcome, "approved">): string {
  if (outcome === "declined") return "File deletion declined by user";
  if (outcome === "unavailable") return "File deletion blocked because confirmation is unavailable";
  return "File deletion blocked because confirmation failed";
}

function deletionBlockedResult(outcome: Exclude<ConfirmationOutcome, "approved">) {
  return {
    result: {
      output: `${confirmationBlockedReason(outcome)}.`,
      exitCode: 1,
      cancelled: false,
      truncated: false,
    },
  };
}

async function confirmFileDeletion(
  command: string,
  hasUI: boolean,
  mode: "tui" | "rpc" | "json" | "print",
  confirm: (title: string, message: string, options?: { timeout?: number }) => Promise<boolean>,
): Promise<ConfirmationOutcome> {
  if (!hasUI) return "unavailable";

  try {
    const confirmed = await confirm(
      "Delete files?",
      `The following command may permanently delete files:\n\n${command}\n\nAllow it to run?`,
      mode === "rpc" ? { timeout: rpcConfirmationTimeoutMs } : undefined,
    );
    return confirmed ? "approved" : "declined";
  } catch {
    return "failed";
  }
}

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "bash") return undefined;

    const command = (event.input as { command?: unknown }).command;
    if (typeof command !== "string" || !isFileDeletionCommand(command)) return undefined;

    const confirmationOutcome = await confirmFileDeletion(
      command,
      ctx.hasUI,
      ctx.mode,
      ctx.ui.confirm.bind(ctx.ui),
    );
    return confirmationOutcome === "approved"
      ? undefined
      : { block: true, reason: confirmationBlockedReason(confirmationOutcome) };
  });

  pi.on("user_bash", async (event, ctx) => {
    if (!isFileDeletionCommand(event.command)) return undefined;

    const confirmationOutcome = await confirmFileDeletion(
      event.command,
      ctx.hasUI,
      ctx.mode,
      ctx.ui.confirm.bind(ctx.ui),
    );
    return confirmationOutcome === "approved" ? undefined : deletionBlockedResult(confirmationOutcome);
  });
}
