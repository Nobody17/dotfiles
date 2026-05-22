export interface SkillReviewCommandOptions {
  skillArgument?: string;
  direct: boolean;
  dryRun: boolean;
  full: boolean;
  mode: "all" | "trigger" | "output";
  noEvals: boolean;
  noLlmJudge: boolean;
  quick: boolean;
  resumeRunDir?: string;
  triggerRuns?: number;
}

export interface SkillCreateCommandOptions {
  skillName?: string;
  targetDir?: string;
  scope?: "agent" | "project" | "custom";
  taskDomain?: string;
  useCases?: string;
  needsScripts?: boolean;
  referenceMaterials?: string;
  noEvals: boolean;
  dryRun: boolean;
}

export interface ParsedArgs<T> {
  options: T;
  errors: string[];
}

interface TokenizedArgs {
  tokens: string[];
  errors: string[];
}

function tokenizeArgs(rawArgs: string | undefined): TokenizedArgs {
  const tokens: string[] = [];
  const errors: string[] = [];
  const input = rawArgs ?? "";
  let currentToken = "";
  let quoteCharacter: '"' | "'" | null = null;
  let escaping = false;

  for (const character of input) {
    if (escaping) {
      currentToken += character;
      escaping = false;
      continue;
    }

    if (character === "\\") {
      escaping = true;
      continue;
    }

    if (quoteCharacter) {
      if (character === quoteCharacter) {
        quoteCharacter = null;
      } else {
        currentToken += character;
      }
      continue;
    }

    if (character === '"' || character === "'") {
      quoteCharacter = character;
      continue;
    }

    if (/\s/.test(character)) {
      if (currentToken.length > 0) {
        tokens.push(currentToken);
        currentToken = "";
      }
      continue;
    }

    currentToken += character;
  }

  if (escaping) currentToken += "\\";
  if (quoteCharacter) errors.push(`Unclosed ${quoteCharacter} quote in command arguments.`);
  if (currentToken.length > 0) tokens.push(currentToken);

  return { tokens, errors };
}

function readOptionValue(
  tokens: string[],
  tokenIndex: number,
  optionName: string,
  errors: string[],
): { value: string | undefined; nextIndex: number } {
  const currentToken = tokens[tokenIndex];
  const equalsIndex = currentToken.indexOf("=");
  if (equalsIndex >= 0) {
    return { value: currentToken.slice(equalsIndex + 1), nextIndex: tokenIndex };
  }

  const nextToken = tokens[tokenIndex + 1];
  if (!nextToken || nextToken.startsWith("--")) {
    errors.push(`${optionName} requires a value.`);
    return { value: undefined, nextIndex: tokenIndex };
  }
  return { value: nextToken, nextIndex: tokenIndex + 1 };
}

function parsePositiveInteger(
  value: string | undefined,
  optionName: string,
  errors: string[],
): number | undefined {
  if (value === undefined) return undefined;
  if (!/^[1-9][0-9]*$/.test(value)) {
    errors.push(`${optionName} must be a positive integer.`);
    return undefined;
  }
  return Number.parseInt(value, 10);
}

export function parseSkillReviewArgs(rawArgs: string | undefined): ParsedArgs<SkillReviewCommandOptions> {
  const tokenized = tokenizeArgs(rawArgs);
  const errors = [...tokenized.errors];
  const positionalArgs: string[] = [];
  const options: SkillReviewCommandOptions = {
    direct: false,
    dryRun: false,
    full: false,
    mode: "all",
    noEvals: false,
    noLlmJudge: false,
    quick: false,
  };

  for (let tokenIndex = 0; tokenIndex < tokenized.tokens.length; tokenIndex++) {
    const token = tokenized.tokens[tokenIndex];

    if (token === "--quick") {
      options.quick = true;
      continue;
    }
    if (token === "--full") {
      options.full = true;
      continue;
    }
    if (token === "--dry-run") {
      options.dryRun = true;
      continue;
    }
    if (token === "--no-evals") {
      options.noEvals = true;
      continue;
    }
    if (token === "--direct") {
      options.direct = true;
      continue;
    }
    if (token === "--no-llm-judge") {
      options.noLlmJudge = true;
      continue;
    }
    if (token === "--trigger-runs" || token.startsWith("--trigger-runs=")) {
      const valueResult = readOptionValue(tokenized.tokens, tokenIndex, "--trigger-runs", errors);
      tokenIndex = valueResult.nextIndex;
      options.triggerRuns = parsePositiveInteger(valueResult.value, "--trigger-runs", errors);
      continue;
    }
    if (token === "--mode" || token.startsWith("--mode=")) {
      const valueResult = readOptionValue(tokenized.tokens, tokenIndex, "--mode", errors);
      tokenIndex = valueResult.nextIndex;
      if (valueResult.value === "all" || valueResult.value === "trigger" || valueResult.value === "output") {
        options.mode = valueResult.value;
      } else if (valueResult.value !== undefined) {
        errors.push("--mode must be one of: all, trigger, output.");
      }
      continue;
    }
    if (token === "--resume" || token.startsWith("--resume=")) {
      const valueResult = readOptionValue(tokenized.tokens, tokenIndex, "--resume", errors);
      tokenIndex = valueResult.nextIndex;
      options.resumeRunDir = valueResult.value;
      continue;
    }
    if (token.startsWith("--")) {
      errors.push(`Unknown option: ${token}`);
      continue;
    }

    positionalArgs.push(token);
  }

  if (options.quick && options.full) {
    errors.push("Use only one of --quick or --full.");
  }
  if (options.quick && options.triggerRuns === undefined) options.triggerRuns = 1;
  if (options.full && options.triggerRuns === undefined) options.triggerRuns = 3;
  if (positionalArgs.length > 0) options.skillArgument = positionalArgs.join(" ");

  return { options, errors };
}

export function parseSkillCreateArgs(rawArgs: string | undefined): ParsedArgs<SkillCreateCommandOptions> {
  const tokenized = tokenizeArgs(rawArgs);
  const errors = [...tokenized.errors];
  const positionalArgs: string[] = [];
  const options: SkillCreateCommandOptions = {
    noEvals: false,
    dryRun: false,
  };

  for (let tokenIndex = 0; tokenIndex < tokenized.tokens.length; tokenIndex++) {
    const token = tokenized.tokens[tokenIndex];

    if (token === "--project") {
      options.scope = "project";
      continue;
    }
    if (token === "--global" || token === "--agent") {
      options.scope = "agent";
      continue;
    }
    if (token === "--scripts") {
      options.needsScripts = true;
      continue;
    }
    if (token === "--no-scripts") {
      options.needsScripts = false;
      continue;
    }
    if (token === "--no-evals") {
      options.noEvals = true;
      continue;
    }
    if (token === "--dry-run") {
      options.dryRun = true;
      continue;
    }
    if (token === "--dir" || token.startsWith("--dir=") || token === "--target-dir" || token.startsWith("--target-dir=")) {
      const valueResult = readOptionValue(tokenized.tokens, tokenIndex, token.startsWith("--dir") ? "--dir" : "--target-dir", errors);
      tokenIndex = valueResult.nextIndex;
      options.targetDir = valueResult.value;
      options.scope = "custom";
      continue;
    }
    if (token === "--domain" || token.startsWith("--domain=")) {
      const valueResult = readOptionValue(tokenized.tokens, tokenIndex, "--domain", errors);
      tokenIndex = valueResult.nextIndex;
      options.taskDomain = valueResult.value;
      continue;
    }
    if (token === "--use-cases" || token.startsWith("--use-cases=") || token === "--use-case" || token.startsWith("--use-case=")) {
      const valueResult = readOptionValue(tokenized.tokens, tokenIndex, "--use-cases", errors);
      tokenIndex = valueResult.nextIndex;
      options.useCases = valueResult.value;
      continue;
    }
    if (token === "--references" || token.startsWith("--references=") || token === "--reference" || token.startsWith("--reference=")) {
      const valueResult = readOptionValue(tokenized.tokens, tokenIndex, "--references", errors);
      tokenIndex = valueResult.nextIndex;
      options.referenceMaterials = valueResult.value;
      continue;
    }
    if (token.startsWith("--")) {
      errors.push(`Unknown option: ${token}`);
      continue;
    }

    positionalArgs.push(token);
  }

  if (positionalArgs.length > 0) options.skillName = positionalArgs.join(" ");

  return { options, errors };
}
