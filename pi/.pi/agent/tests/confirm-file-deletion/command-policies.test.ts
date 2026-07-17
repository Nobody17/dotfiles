import assert from "node:assert/strict";
import test from "node:test";

import { assessFileDeletion, type AssessmentKind } from "../../extensions/confirm-file-deletion/assessment.ts";

type PolicyCase = {
  source: string;
  kind: AssessmentKind;
  policy?: string;
};

const policyCases: PolicyCase[] = [
  { source: "command -- rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { source: "sudo --prompt prompt rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { source: "doas -u root rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { source: "exec -a replacement rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { source: "nice -n 5 rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { source: "nohup rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { source: "setsid rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { source: "time -f '%E' rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { source: "env KEEP=1 rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { source: "env --split-string='rm obsolete.txt'", kind: "deletion", policy: "direct-rm" },
  { source: "busybox rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { source: "toybox rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { source: "xargs --replace=ITEM rm ITEM", kind: "deletion", policy: "direct-rm" },
  { source: "find . -execdir rm {} +", kind: "deletion", policy: "direct-rm" },
  { source: "find . -ok rm {} \\;", kind: "deletion", policy: "direct-rm" },
  { source: "find . -okdir rm {} \\;", kind: "deletion", policy: "direct-rm" },
  { source: "rsync --remove-source-files source target", kind: "deletion", policy: "rsync-remove-source-files" },
  { source: "sh -c -- 'rm obsolete.txt'", kind: "deletion", policy: "direct-rm" },
  { source: "dash -c 'rm obsolete.txt'", kind: "deletion", policy: "direct-rm" },
  { source: "ksh -c 'rm obsolete.txt'", kind: "deletion", policy: "direct-rm" },
  { source: "mksh -c 'rm obsolete.txt'", kind: "deletion", policy: "direct-rm" },
  { source: "zsh --command='rm obsolete.txt'", kind: "deletion", policy: "direct-rm" },
  { source: "fish -c 'rm obsolete.txt'", kind: "unknown", policy: "unsupported-interpreter" },
  { source: "bash script.sh", kind: "safe" },
  { source: "timeout --signal=TERM 5 rm obsolete.txt", kind: "deletion", policy: "direct-rm" },
  { source: "timeout --help rm obsolete.txt", kind: "safe" },
  { source: "rm -- -", kind: "deletion", policy: "direct-rm" },
  { source: "rm -f", kind: "safe" },
  { source: "git clean --dry-run -fd", kind: "safe" },
  { source: "git rm --cached obsolete.txt", kind: "safe" },
  { source: "git rm --pathspec-from-file=paths", kind: "deletion", policy: "git-rm" },
  { source: "find . -name '-delete'", kind: "safe" },
  { source: "find . -printf -delete", kind: "safe" },
  { source: "xargs rm --help", kind: "safe" },
  { source: "env --help rm obsolete.txt", kind: "safe" },
  { source: "sudo -u", kind: "unknown", policy: "wrapper-options" },
  { source: "env -S", kind: "unknown", policy: "env-options" },
  { source: "timeout -k rm obsolete.txt", kind: "unknown", policy: "timeout-options" },
];

for (const policyCase of policyCases) {
  test(`classifies ${policyCase.source}`, () => {
    const assessment = assessFileDeletion(policyCase.source);

    assert.equal(assessment.kind, policyCase.kind);
    if (policyCase.policy !== undefined) {
      assert.ok(assessment.kind !== "safe");
      assert.ok(assessment.findings.some((finding) => finding.policy === policyCase.policy));
    }
  });
}
