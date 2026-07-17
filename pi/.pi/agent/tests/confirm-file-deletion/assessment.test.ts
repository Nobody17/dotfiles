import assert from "node:assert/strict";
import test from "node:test";

import {
  assessFileDeletion,
  isFileDeletionCommand,
  type AssessmentKind,
} from "../../extensions/confirm-file-deletion/assessment.ts";

type AssessmentCase = {
  description: string;
  source: string;
  kind: AssessmentKind;
  policy?: string;
};

const assessmentCases: AssessmentCase[] = [
  { description: "direct rm", source: "rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { description: "absolute rmdir", source: "/bin/rmdir empty", kind: "deletion", policy: "direct-rmdir" },
  { description: "unlink after a chain", source: "cd project && unlink socket", kind: "deletion", policy: "direct-unlink" },
  { description: "redirection before rm", source: ">/tmp/log rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { description: "redirection after sudo", source: "sudo 2>/dev/null rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { description: "brace expansion operand", source: "rm {old,new}.txt", kind: "deletion", policy: "direct-rm" },
  { description: "lone dash operand", source: "rm -", kind: "deletion", policy: "direct-rm" },
  { description: "timeout wrapper", source: "timeout 5 rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { description: "env split string", source: "env -S'rm obsolete.txt'", kind: "deletion", policy: "direct-rm" },
  { description: "xargs replacement option", source: "xargs -0I ITEM rm ITEM", kind: "deletion", policy: "direct-rm" },
  { description: "find delete", source: "find cache -type f -delete", kind: "deletion", policy: "find-delete" },
  { description: "find exec", source: "find . -exec rm {} \\;", kind: "deletion", policy: "direct-rm" },
  { description: "git clean", source: "git clean -fd", kind: "deletion", policy: "git-clean" },
  { description: "git rm", source: "git -C project rm stale", kind: "deletion", policy: "git-rm" },
  { description: "shred remove", source: "shred --remove secrets.txt", kind: "deletion", policy: "shred-remove" },
  { description: "rsync delete", source: "rsync --delete source/ target/", kind: "deletion", policy: "rsync-delete" },
  { description: "shell command string", source: "bash -lc 'rm obsolete.txt'", kind: "deletion", policy: "direct-rm" },
  { description: "nested eval", source: "eval 'eval rm obsolete.txt'", kind: "deletion", policy: "direct-rm" },
  { description: "command substitution", source: "echo \"$(rm obsolete.txt)\"", kind: "deletion", policy: "direct-rm" },
  { description: "process substitution", source: "cat <(rm obsolete.txt)", kind: "deletion", policy: "direct-rm" },
  { description: "arithmetic command substitution", source: "echo $(( $(rm obsolete.txt) + 1 ))", kind: "deletion", policy: "direct-rm" },
  { description: "unquoted heredoc", source: "cat <<EOF\n$(rm obsolete.txt)\nEOF", kind: "deletion", policy: "direct-rm" },
  { description: "assignment substitution", source: "value=$(rm obsolete.txt)", kind: "deletion", policy: "direct-rm" },
  { description: "function body", source: "remove() { rm obsolete.txt; }", kind: "deletion", policy: "direct-rm" },
  { description: "subshell", source: "(rm obsolete.txt)", kind: "deletion", policy: "direct-rm" },
  { description: "brace group", source: "{ rm obsolete.txt; }", kind: "deletion", policy: "direct-rm" },
  { description: "coprocess", source: "coproc { rm obsolete.txt; }", kind: "deletion", policy: "direct-rm" },
  { description: "conditional branch", source: "if false; then rm obsolete.txt; fi", kind: "deletion", policy: "direct-rm" },
  { description: "loop body", source: "while false; do rm obsolete.txt; done", kind: "deletion", policy: "direct-rm" },
  { description: "case arm", source: "case value in value) rm obsolete.txt;; esac", kind: "deletion", policy: "direct-rm" },
  { description: "resolved command variable", source: "deleter=rm; \"$deleter\" obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { description: "dynamic command variable", source: "\"$deleter\" obsolete.txt", kind: "unknown", policy: "dynamic-command-name" },
  { description: "stale assignment invalidation", source: "program=printf; program=$unknown; \"$program\" safe", kind: "unknown", policy: "dynamic-command-name" },
  { description: "unset invalidation", source: "program=printf; unset program; \"$program\" safe", kind: "unknown", policy: "dynamic-command-name" },
  { description: "rm redirect only", source: "rm >/tmp/log", kind: "safe" },
  { description: "shred without removal", source: "shred -u", kind: "safe" },
  { description: "quoted heredoc", source: "cat <<'EOF'\n$(rm obsolete.txt)\nEOF", kind: "safe" },
  { description: "resolved safe command", source: "program=printf; \"$program\" safe", kind: "safe" },
  { description: "rm help", source: "rm --help obsolete.txt", kind: "safe" },
  { description: "git clean dry run", source: "git clean -n", kind: "safe" },
  { description: "unrecognised command", source: "python -c 'import os; os.unlink(\"x\")'", kind: "safe" },
];

for (const assessmentCase of assessmentCases) {
  test(`assesses ${assessmentCase.description}`, () => {
    const assessment = assessFileDeletion(assessmentCase.source);

    assert.equal(assessment.kind, assessmentCase.kind);
    if (assessmentCase.policy !== undefined) {
      assert.ok(assessment.kind !== "safe");
      assert.ok(assessment.findings.some((finding) => finding.policy === assessmentCase.policy));
    }
  });
}

const regressionCases: AssessmentCase[] = [
  { description: "quoted command name", source: "'rm' obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { description: "command name assembled from literal fragments", source: "r''m obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { description: "quoted assignment prefix", source: "FOO=\"value\" rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { description: "command wrapper unlink", source: "command unlink temporary.sock", kind: "deletion", policy: "direct-unlink" },
  { description: "backtick substitution", source: "echo `rm obsolete.txt`", kind: "deletion", policy: "direct-rm" },
  { description: "quoted find exec", source: "find . -exec 'rm' {} \\;", kind: "deletion", policy: "direct-rm" },
  { description: "find ok", source: "find . -ok rm {} \\;", kind: "deletion", policy: "direct-rm" },
  { description: "pipeline", source: "printf obsolete.txt | xargs rm", kind: "deletion", policy: "xargs-dispatch" },
  { description: "for word substitution", source: "for value in $(rm obsolete.txt); do printf safe; done", kind: "deletion", policy: "direct-rm" },
  { description: "redirect target substitution", source: "printf safe >$(rm obsolete.txt)", kind: "deletion", policy: "direct-rm" },
  { description: "assignment prefix substitution", source: "value=$(rm obsolete.txt) printf safe", kind: "deletion", policy: "direct-rm" },
  { description: "rm text in single-quoted argument", source: "echo 'rm obsolete.txt'", kind: "safe" },
  { description: "rm arithmetic variable", source: "echo $((rm + 1))", kind: "safe" },
  { description: "rm grep search term", source: "grep -R rm documentation", kind: "safe" },
  { description: "npm remove", source: "npm remove typescript", kind: "safe" },
  { description: "find print", source: "find cache -type f -print", kind: "safe" },
  { description: "rm version", source: "rm --version file", kind: "safe" },
  { description: "uppercase unrelated command", source: "RM obsolete.txt", kind: "safe" },
  { description: "commented command substitution", source: "echo safe # $(rm obsolete.txt)", kind: "safe" },
  { description: "find exec non-deletion", source: "find . -exec echo -delete \\;", kind: "safe" },
  { description: "command lookup", source: "command -v rm obsolete.txt", kind: "safe" },
  { description: "shred help", source: "shred -u --help obsolete.txt", kind: "safe" },
  { description: "script file c argument", source: "bash safe-script.sh -c 'rm obsolete.txt'", kind: "safe" },
];

for (const regressionCase of regressionCases) {
  test(`retains regression coverage for ${regressionCase.description}`, () => {
    const assessment = assessFileDeletion(regressionCase.source);

    assert.equal(assessment.kind, regressionCase.kind);
    if (regressionCase.policy !== undefined) {
      assert.ok(assessment.kind !== "safe");
      assert.ok(assessment.findings.some((finding) => finding.policy === regressionCase.policy));
    }
  });
}

test("keeps a recovered deletion ahead of parse errors", () => {
  const assessment = assessFileDeletion("rm obsolete.txt; if then");

  assert.equal(assessment.kind, "deletion");
  assert.ok(assessment.findings.some((finding) => finding.policy === "direct-rm"));
  assert.ok(assessment.findings.some((finding) => finding.policy === "parse-error"));
});

test("fails closed for a parse error without a recovered deletion", () => {
  const assessment = assessFileDeletion("if then");

  assert.equal(assessment.kind, "unknown");
  assert.ok(assessment.findings.some((finding) => finding.policy === "parse-error"));
});

test("fails closed at each deterministic assessment limit", () => {
  const source = "echo safe";
  const sourceLimit = assessFileDeletion(source, { maxSourceLength: source.length - 1 });
  const nodeLimit = assessFileDeletion(source, { maxNodes: 1 });

  assert.equal(sourceLimit.kind, "unknown");
  assert.equal(nodeLimit.kind, "unknown");
  assert.ok(sourceLimit.findings.some((finding) => finding.policy === "assessment-limit"));
  assert.ok(nodeLimit.findings.some((finding) => finding.policy === "assessment-limit"));
});

test("keeps deletion result when a later limit is exceeded", () => {
  const assessment = assessFileDeletion("rm obsolete.txt; echo safe", { maxNodes: 3 });

  assert.equal(assessment.kind, "deletion");
  assert.ok(assessment.findings.some((finding) => finding.policy === "direct-rm"));
});

test("fails closed when nested command parsing reaches its depth or aggregate-source limit", () => {
  const depthLimited = assessFileDeletion("eval 'rm obsolete.txt'", { maxCommandStringDepth: 0 });
  const aggregateLimited = assessFileDeletion("bash -c 'rm obsolete.txt'", { maxAggregateSourceLength: 20 });

  assert.equal(depthLimited.kind, "unknown");
  assert.equal(aggregateLimited.kind, "unknown");
  assert.ok(depthLimited.findings.some((finding) => finding.policy === "assessment-limit"));
  assert.ok(aggregateLimited.findings.some((finding) => finding.policy === "assessment-limit"));
});

test("preserves a deletion result even when the finding limit is exhausted", () => {
  const assessment = assessFileDeletion("rm obsolete.txt", { maxFindings: 0 });

  assert.equal(assessment.kind, "deletion");
});

test("keeps the compatibility predicate fail-closed", () => {
  assert.equal(isFileDeletionCommand("printf safe"), false);
  assert.equal(isFileDeletionCommand("rm obsolete.txt"), true);
  assert.equal(isFileDeletionCommand("if then"), true);
});
