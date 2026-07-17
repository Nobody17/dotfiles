import type {
  ArithmeticExpression,
  AssignmentPrefix,
  CaseItem,
  CompoundList,
  Node,
  Redirect,
  Script,
  Statement,
  TestExpression,
  Word,
  WordPart,
} from "unbash";

import {
  assessCommandPolicy,
  basename,
  literalWordValue,
  policyFinding,
  simpleParameterName,
  type PolicyContext,
} from "./command-policies.ts";
import type { AssessmentFinding } from "./assessment.ts";

export type ConstantState = Map<string, string>;

export type TraversalEnvironment = {
  enter: (node: { pos?: number; end?: number }) => boolean;
  addFinding: (finding: AssessmentFinding) => void;
  assessCommandText: (source: string, span?: { start: number; end: number }) => void;
};

function spanOf(node: { pos?: number; end?: number } | undefined): { start: number; end: number } | undefined {
  if (typeof node?.pos !== "number" || typeof node.end !== "number") return undefined;
  return { start: node.pos, end: node.end };
}

function cloneState(state: ConstantState): ConstantState {
  return new Map(state);
}

function visitWords(words: readonly Word[], state: ConstantState, environment: TraversalEnvironment): void {
  for (const word of words) visitWord(word, state, environment);
}

function visitAssignment(assignment: AssignmentPrefix, state: ConstantState, environment: TraversalEnvironment): void {
  if (!environment.enter(assignment)) return;
  if (assignment.value !== undefined) visitWord(assignment.value, state, environment);
  for (const item of assignment.array ?? []) visitWord(item, state, environment);
}

function updateAssignment(state: ConstantState, assignment: AssignmentPrefix): void {
  if (assignment.name === undefined || assignment.array !== undefined || assignment.index !== undefined) return;
  const value = literalWordValue(assignment.value);
  if (value === undefined) {
    state.delete(assignment.name);
    return;
  }
  if (assignment.append) {
    const existing = state.get(assignment.name);
    if (existing === undefined) state.delete(assignment.name);
    else state.set(assignment.name, `${existing}${value}`);
    return;
  }
  state.set(assignment.name, value);
}

function updateAssignmentOnlyState(command: Extract<Node, { type: "Command" }>, state: ConstantState): void {
  for (const assignment of command.prefix) updateAssignment(state, assignment);
}

function updateAssignmentBuiltinState(
  command: Extract<Node, { type: "Command" }>,
  commandName: string,
  state: ConstantState,
): void {
  if (["export", "readonly", "declare", "typeset", "local"].includes(commandName)) {
    for (const word of command.suffix) {
      const literal = literalWordValue(word);
      const text = literal ?? word.text;
      const match = /^([A-Za-z_][A-Za-z0-9_]*)(\+?=)(.*)$/.exec(text);
      if (match === null) {
        if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(text)) state.delete(text);
        else if (literal === undefined) state.clear();
        continue;
      }
      const [, name, operator, value] = match;
      if (literal === undefined) {
        state.delete(name);
      } else if (operator === "+=") {
        const existing = state.get(name);
        if (existing === undefined) state.delete(name);
        else state.set(name, `${existing}${value}`);
      } else {
        state.set(name, value);
      }
    }
    return;
  }

  if (commandName === "unset") {
    for (const word of command.suffix) {
      const name = literalWordValue(word);
      if (name === undefined) {
        state.clear();
        return;
      }
      if (name.startsWith("-")) continue;
      if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) state.delete(name);
    }
  }
}

function resolvedCommandName(word: Word, state: ConstantState): string | undefined {
  const literal = literalWordValue(word);
  if (literal !== undefined) return literal;
  const parameter = simpleParameterName(word);
  return parameter === undefined ? undefined : state.get(parameter);
}

function assessInvocation(
  words: Word[],
  state: ConstantState,
  environment: TraversalEnvironment,
  span?: { start: number; end: number },
): void {
  if (words.length === 0) return;
  const commandWord = words[0];
  const resolvedName = resolvedCommandName(commandWord, state);
  if (resolvedName === undefined) {
    environment.addFinding({
      kind: "unknown",
      policy: "dynamic-command-name",
      message: "Dynamic command name cannot be resolved statically",
      span: span ?? spanOf(commandWord),
    });
    return;
  }

  const policyContext: PolicyContext = {
    assessCommandText: environment.assessCommandText,
    assessNestedInvocation: (nestedWords) => assessInvocation(nestedWords, state, environment),
  };
  const policyDecision = assessCommandPolicy(resolvedName, words.slice(1), policyContext);
  if (policyDecision.kind === "deletion" || policyDecision.kind === "unknown") {
    environment.addFinding(policyFinding(policyDecision, span ?? spanOf(commandWord)));
  }
}

function visitCommand(
  command: Extract<Node, { type: "Command" }>,
  state: ConstantState,
  environment: TraversalEnvironment,
): void {
  if (!environment.enter(command)) return;

  if (command.name === undefined) {
    for (const assignment of command.prefix) visitAssignment(assignment, state, environment);
    for (const redirect of command.redirects) visitRedirect(redirect, state, environment);
    updateAssignmentOnlyState(command, state);
    return;
  }

  const commandName = resolvedCommandName(command.name, state);
  assessInvocation([command.name, ...command.suffix], state, environment, spanOf(command.name));

  for (const assignment of command.prefix) visitAssignment(assignment, state, environment);
  visitWord(command.name, state, environment);
  visitWords(command.suffix, state, environment);
  for (const redirect of command.redirects) visitRedirect(redirect, state, environment);

  if (commandName !== undefined) updateAssignmentBuiltinState(command, basename(commandName), state);
}

function visitPipeline(
  pipeline: Extract<Node, { type: "Pipeline" }>,
  state: ConstantState,
  environment: TraversalEnvironment,
): void {
  if (!environment.enter(pipeline)) return;
  if (pipeline.time && pipeline.commands.length === 1 && pipeline.commands[0]?.type === "Command") {
    const command = pipeline.commands[0];
    const timeWord = {
      text: "time",
      value: "time",
      pos: pipeline.pos,
      end: pipeline.pos + 4,
    } as Word;
    assessInvocation([timeWord, command.name, ...command.suffix].filter((word): word is Word => word !== undefined), state, environment, spanOf(timeWord));
  }
  for (const command of pipeline.commands) visitNode(command, cloneState(state), environment);
  state.clear();
}

function visitAndOr(
  andOr: Extract<Node, { type: "AndOr" }>,
  state: ConstantState,
  environment: TraversalEnvironment,
): void {
  if (!environment.enter(andOr)) return;
  for (const command of andOr.commands) visitNode(command, cloneState(state), environment);
  state.clear();
}

function visitCompoundList(list: CompoundList, state: ConstantState, environment: TraversalEnvironment): void {
  if (!environment.enter(list)) return;
  for (const statement of list.commands) visitStatement(statement, state, environment);
}

function visitCaseItem(item: CaseItem, state: ConstantState, environment: TraversalEnvironment): void {
  if (!environment.enter(item)) return;
  visitWords(item.pattern, state, environment);
  visitCompoundList(item.body, state, environment);
}

function visitTestExpression(expression: TestExpression, state: ConstantState, environment: TraversalEnvironment): void {
  if (!environment.enter(expression)) return;
  switch (expression.type) {
    case "TestUnary":
      visitWord(expression.operand, state, environment);
      return;
    case "TestBinary":
      visitWord(expression.left, state, environment);
      visitWord(expression.right, state, environment);
      return;
    case "TestLogical":
      visitTestExpression(expression.left, state, environment);
      visitTestExpression(expression.right, state, environment);
      return;
    case "TestNot":
      visitTestExpression(expression.operand, state, environment);
      return;
    case "TestGroup":
      visitTestExpression(expression.expression, state, environment);
  }
}

function visitArithmetic(expression: ArithmeticExpression | undefined, state: ConstantState, environment: TraversalEnvironment): void {
  if (expression === undefined || !environment.enter(expression)) return;
  switch (expression.type) {
    case "ArithmeticBinary":
      visitArithmetic(expression.left, state, environment);
      visitArithmetic(expression.right, state, environment);
      return;
    case "ArithmeticUnary":
      visitArithmetic(expression.operand, state, environment);
      return;
    case "ArithmeticTernary":
      visitArithmetic(expression.test, state, environment);
      visitArithmetic(expression.consequent, state, environment);
      visitArithmetic(expression.alternate, state, environment);
      return;
    case "ArithmeticGroup":
      visitArithmetic(expression.expression, state, environment);
      return;
    case "ArithmeticCommandExpansion":
      if (expression.script === undefined) {
        environment.addFinding({
          kind: "unknown",
          policy: "unparsed-expansion",
          message: "An arithmetic command substitution could not be parsed",
          span: spanOf(expression),
        });
      } else {
        traverseScript(expression.script, cloneState(state), environment);
      }
      return;
    case "ArithmeticWord":
      return;
  }
}

function visitWordPart(part: WordPart, state: ConstantState, environment: TraversalEnvironment): void {
  if (part.type === "Literal" || part.type === "SingleQuoted" || part.type === "AnsiCQuoted" || part.type === "SimpleExpansion" || part.type === "ExtendedGlob" || part.type === "BraceExpansion") {
    return;
  }
  if (part.type === "DoubleQuoted" || part.type === "LocaleString") {
    for (const child of part.parts) visitWordPart(child, state, environment);
    return;
  }
  if (part.type === "CommandExpansion" || part.type === "ProcessSubstitution") {
    if (part.script === undefined) {
      environment.addFinding({
        kind: "unknown",
        policy: "unparsed-expansion",
        message: "A command substitution could not be parsed",
      });
    } else {
      traverseScript(part.script, cloneState(state), environment);
    }
    return;
  }
  if (part.type === "ArithmeticExpansion") {
    visitArithmetic(part.expression, state, environment);
    return;
  }
  if (part.type === "ParameterExpansion") {
    if (part.operand !== undefined) visitWord(part.operand, state, environment);
    if (part.slice !== undefined) {
      visitWord(part.slice.offset, state, environment);
      if (part.slice.length !== undefined) visitWord(part.slice.length, state, environment);
    }
    if (part.replace !== undefined) {
      visitWord(part.replace.pattern, state, environment);
      visitWord(part.replace.replacement, state, environment);
    }
  }
}

function visitWord(word: Word, state: ConstantState, environment: TraversalEnvironment): void {
  if (!environment.enter(word)) return;
  for (const part of word.parts ?? []) visitWordPart(part, state, environment);
}

function visitRedirect(redirect: Redirect, state: ConstantState, environment: TraversalEnvironment): void {
  if (!environment.enter(redirect)) return;
  if (redirect.target !== undefined) visitWord(redirect.target, state, environment);
  if (!redirect.heredocQuoted && redirect.body !== undefined) visitWord(redirect.body, state, environment);
}

function visitStatement(statement: Statement, state: ConstantState, environment: TraversalEnvironment): void {
  if (!environment.enter(statement)) return;
  visitNode(statement.command, state, environment);
  for (const redirect of statement.redirects) visitRedirect(redirect, state, environment);
}

function visitNode(node: Node, state: ConstantState, environment: TraversalEnvironment): void {
  switch (node.type) {
    case "Command":
      visitCommand(node, state, environment);
      return;
    case "Pipeline":
      visitPipeline(node, state, environment);
      return;
    case "AndOr":
      visitAndOr(node, state, environment);
      return;
    case "Statement":
      visitStatement(node, state, environment);
      return;
    case "CompoundList":
      visitCompoundList(node, state, environment);
      return;
    case "If":
      if (!environment.enter(node)) return;
      visitCompoundList(node.clause, cloneState(state), environment);
      visitCompoundList(node.then, cloneState(state), environment);
      if (node.else !== undefined) {
        if (node.else.type === "If") visitNode(node.else, cloneState(state), environment);
        else visitCompoundList(node.else, cloneState(state), environment);
      }
      state.clear();
      return;
    case "For":
    case "Select":
      if (!environment.enter(node)) return;
      visitWord(node.name, state, environment);
      visitWords(node.wordlist, state, environment);
      visitCompoundList(node.body, cloneState(state), environment);
      state.clear();
      return;
    case "ArithmeticFor":
      if (!environment.enter(node)) return;
      visitArithmetic(node.initialize, state, environment);
      visitArithmetic(node.test, state, environment);
      visitArithmetic(node.update, state, environment);
      visitCompoundList(node.body, cloneState(state), environment);
      state.clear();
      return;
    case "While":
      if (!environment.enter(node)) return;
      visitCompoundList(node.clause, cloneState(state), environment);
      visitCompoundList(node.body, cloneState(state), environment);
      state.clear();
      return;
    case "Function":
      if (!environment.enter(node)) return;
      visitNode(node.body, cloneState(state), environment);
      for (const redirect of node.redirects) visitRedirect(redirect, state, environment);
      state.clear();
      return;
    case "Subshell":
    case "BraceGroup":
      if (!environment.enter(node)) return;
      visitCompoundList(node.body, cloneState(state), environment);
      state.clear();
      return;
    case "Case":
      if (!environment.enter(node)) return;
      visitWord(node.word, state, environment);
      for (const item of node.items) visitCaseItem(item, cloneState(state), environment);
      state.clear();
      return;
    case "Coproc":
      if (!environment.enter(node)) return;
      visitNode(node.body, cloneState(state), environment);
      for (const redirect of node.redirects) visitRedirect(redirect, state, environment);
      state.clear();
      return;
    case "TestCommand":
      if (!environment.enter(node)) return;
      visitTestExpression(node.expression, state, environment);
      return;
    case "ArithmeticCommand":
      if (!environment.enter(node)) return;
      visitArithmetic(node.expression, state, environment);
  }
}

export function traverseScript(script: Script, state: ConstantState, environment: TraversalEnvironment): void {
  if (!environment.enter(script)) return;
  for (const statement of script.commands) visitStatement(statement, state, environment);
}
