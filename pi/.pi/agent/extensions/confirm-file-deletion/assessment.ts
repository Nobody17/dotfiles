import { parse, type Script } from "unbash";

import { traverseScript, type TraversalEnvironment } from "./ast-traversal.ts";

export type AssessmentKind = "safe" | "deletion" | "unknown";

export type AssessmentFinding = {
  kind: "deletion" | "unknown";
  policy: string;
  message: string;
  span?: { start: number; end: number };
};

export type DeletionAssessment =
  | { kind: "safe" }
  | { kind: "deletion"; findings: AssessmentFinding[] }
  | { kind: "unknown"; findings: AssessmentFinding[] };

export type AssessmentLimits = {
  maxSourceLength: number;
  maxAggregateSourceLength: number;
  maxCommandStringDepth: number;
  maxNodes: number;
  maxFindings: number;
};

export type AssessmentOptions = Partial<AssessmentLimits>;

export const defaultAssessmentLimits: AssessmentLimits = {
  maxSourceLength: 128 * 1024,
  maxAggregateSourceLength: 512 * 1024,
  maxCommandStringDepth: 32,
  maxNodes: 50_000,
  maxFindings: 100,
};

type ParsedScript = Script & { errors?: Array<{ message: string; pos: number }> };

class AssessmentCollector {
  readonly findings: AssessmentFinding[] = [];
  readonly limits: AssessmentLimits;
  private aggregateSourceLength: number;
  private visitedNodes = 0;
  private commandStringDepth = 0;
  private limitExceeded = false;
  private findingsLimitExceeded = false;
  private detectedDeletion = false;
  private detectedUnknown = false;

  constructor(sourceLength: number, options: AssessmentOptions) {
    this.limits = { ...defaultAssessmentLimits, ...options };
    this.aggregateSourceLength = sourceLength;
  }

  addFinding(finding: AssessmentFinding): void {
    if (finding.kind === "deletion") this.detectedDeletion = true;
    else this.detectedUnknown = true;
    if (this.findingsLimitExceeded) return;
    if (this.findings.some((existing) => (
      existing.kind === finding.kind
      && existing.policy === finding.policy
      && existing.span?.start === finding.span?.start
      && existing.span?.end === finding.span?.end
    ))) return;

    if (this.findings.length >= this.limits.maxFindings) {
      this.findingsLimitExceeded = true;
      this.addLimitFinding("The maximum number of assessment findings was exceeded");
      return;
    }
    this.findings.push(finding);
  }

  enter(node: { pos?: number; end?: number }): boolean {
    if (this.limitExceeded) return false;
    this.visitedNodes += 1;
    if (this.visitedNodes <= this.limits.maxNodes) return true;

    this.limitExceeded = true;
    this.addLimitFinding("The maximum number of AST and word nodes was exceeded", node);
    return false;
  }

  assessNestedCommandText(source: string, span?: { start: number; end: number }): void {
    if (this.limitExceeded) return;
    if (this.commandStringDepth >= this.limits.maxCommandStringDepth) {
      this.limitExceeded = true;
      this.addLimitFinding("The maximum nested command-string depth was exceeded", span);
      return;
    }
    if (this.aggregateSourceLength + source.length > this.limits.maxAggregateSourceLength) {
      this.limitExceeded = true;
      this.addLimitFinding("The maximum aggregate parsed source length was exceeded", span);
      return;
    }

    this.commandStringDepth += 1;
    this.aggregateSourceLength += source.length;
    try {
      this.assessParsedSource(source);
    } catch {
      this.addFinding({
        kind: "unknown",
        policy: "parser-exception",
        message: "The Bash parser failed unexpectedly while assessing a command string",
        span,
      });
    } finally {
      this.commandStringDepth -= 1;
    }
  }

  assessParsedSource(source: string): void {
    let ast: ParsedScript;
    try {
      ast = parse(source);
    } catch {
      this.addFinding({
        kind: "unknown",
        policy: "parser-exception",
        message: "The Bash parser failed unexpectedly",
      });
      return;
    }

    for (const error of ast.errors ?? []) {
      this.addFinding({
        kind: "unknown",
        policy: "parse-error",
        message: `Bash syntax could not be fully parsed: ${error.message}`,
        span: { start: error.pos, end: error.pos },
      });
    }

    const environment: TraversalEnvironment = {
      enter: (node) => this.enter(node),
      addFinding: (finding) => this.addFinding(finding),
      assessCommandText: (commandText, span) => this.assessNestedCommandText(commandText, span),
    };
    traverseScript(ast, new Map(), environment);
  }

  result(): DeletionAssessment {
    if (this.detectedDeletion) return { kind: "deletion", findings: this.findings };
    if (this.detectedUnknown || this.findingsLimitExceeded) return { kind: "unknown", findings: this.findings };
    return { kind: "safe" };
  }

  markSourceLimitExceeded(): void {
    this.limitExceeded = true;
    this.addLimitFinding("The maximum top-level source length was exceeded");
  }

  private addLimitFinding(message: string, node?: { pos?: number; end?: number } | { start: number; end: number }): void {
    const span = node !== undefined && "start" in node
      ? node
      : typeof node?.pos === "number" && typeof node.end === "number"
        ? { start: node.pos, end: node.end }
        : undefined;
    this.detectedUnknown = true;
    const finding: AssessmentFinding = {
      kind: "unknown",
      policy: "assessment-limit",
      message,
      span,
    };
    if (this.findings.some((existing) => existing.policy === finding.policy && existing.message === finding.message)) return;
    if (this.findings.length < this.limits.maxFindings) this.findings.push(finding);
  }
}

/**
 * Conservatively assesses Bash source for known file-deletion commands.
 * Unknown parser input and assessment-limit failures require confirmation.
 */
export function assessFileDeletion(source: string, options: AssessmentOptions = {}): DeletionAssessment {
  const collector = new AssessmentCollector(source.length, options);
  if (source.length > collector.limits.maxSourceLength) {
    collector.markSourceLimitExceeded();
    return collector.result();
  }

  try {
    collector.assessParsedSource(source);
  } catch {
    collector.addFinding({
      kind: "unknown",
      policy: "assessment-exception",
      message: "File-deletion assessment failed unexpectedly",
    });
  }
  return collector.result();
}

/** @deprecated Use assessFileDeletion() to obtain findings and failure reasons. */
export function isFileDeletionCommand(command: string): boolean {
  return assessFileDeletion(command).kind !== "safe";
}
