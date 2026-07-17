import assert from "node:assert/strict";
import test from "node:test";

import { isFileDeletionCommand } from "../extensions/confirm-file-deletion.ts";

const deletionCommandCases = [
  { description: "a direct rm invocation", command: "rm obsolete.txt" },
  { description: "an absolute rm path with combined options", command: "/bin/rm -rf build" },
  { description: "rmdir after a chained command", command: "cd project && rmdir empty-directory" },
  { description: "unlink through the command wrapper", command: "command unlink temporary.sock" },
  { description: "rm through sudo", command: "sudo rm -f /tmp/temporary-file" },
  { description: "rm through env assignments", command: "env KEEP_LOGS=1 rm stale.log" },
  { description: "find -delete", command: "find cache -type f -delete" },
  { description: "find -exec rm", command: "find . -name '*.tmp' -exec rm {} \\;" },
  { description: "find -ok rm", command: "find . -ok rm {} \\;" },
  { description: "rm invoked by xargs", command: "printf '%s\\0' old.txt | xargs -0 rm" },
  { description: "git clean without dry-run", command: "git clean -fd" },
  { description: "shred with removal enabled", command: "shred --remove secrets.txt" },
  { description: "rm after a multiline shell command", command: "set -e\nrm obsolete.txt" },
  { description: "a quoted command name", command: "'rm' obsolete.txt" },
  { description: "a command name assembled from quoted fragments", command: "r''m obsolete.txt" },
  { description: "rm after a quoted environment assignment", command: "FOO=\"value\" rm obsolete.txt" },
  { description: "rm in env split-string", command: "env -S 'rm obsolete.txt'" },
  { description: "rm in a bash command string", command: "bash -lc \"rm obsolete.txt\"" },
  { description: "rm in a sh command string after an option terminator", command: "sh -c -- 'rm obsolete.txt'" },
  { description: "rm in command substitution", command: "echo \"$(rm obsolete.txt)\"" },
  { description: "rm in command substitution inside arithmetic expansion", command: "echo $(( $(rm obsolete.txt) + 1 ))" },
  { description: "rm in backtick substitution", command: "echo `rm obsolete.txt`" },
  { description: "a quoted rm command in find -exec", command: "find . -exec 'rm' {} \\;" },
  { description: "rm after an xargs replacement option", command: "printf '%s\\0' obsolete.txt | xargs -I ITEM rm ITEM" },
  { description: "rm after a sudo option with an argument", command: "sudo --prompt confirmation rm obsolete.txt" },
  { description: "git rm after a global option", command: "git -C repository rm obsolete.txt" },
  { description: "rm inside a brace group", command: "{ rm obsolete.txt; }" },
  { description: "rm after exec's alternate process-name option", command: "exec -a custom-name rm obsolete.txt" },
  { description: "a deletion command read from a shell variable", command: "deleter=rm; \"$deleter\" obsolete.txt" },
  { description: "rm through BusyBox", command: "busybox rm obsolete.txt" },
  { description: "git rm with pathspecs read from a file", command: "git rm --pathspec-from-file=paths.txt" },
  {
    description: "rm inside a shell function body",
    command: "delete_generated_files() { rm obsolete.txt; }\ndelete_generated_files",
  },
] as const;

for (const { description, command } of deletionCommandCases) {
  test(`detects ${description} as file deletion`, () => {
    assert.equal(isFileDeletionCommand(command), true);
  });
}

const nonDeletionCommandCases = [
  { description: "rm text inside a single-quoted echo argument", command: "echo 'rm obsolete.txt'" },
  { description: "an rm-named arithmetic variable", command: "echo $((rm + 1))" },
  { description: "rm used as a grep search term", command: "grep -R rm documentation" },
  { description: "npm remove", command: "npm remove typescript" },
  { description: "find with a print action", command: "find cache -type f -print" },
  { description: "-delete used as a find name argument", command: "find . -name '-delete'" },
  { description: "-delete used as a find printf argument", command: "find . -printf -delete" },
  { description: "shred without file removal", command: "shred secrets.txt" },
  { description: "-u used as a shred file operand", command: "shred -- -u" },
  { description: "git clean with a short dry-run option", command: "git clean -n" },
  { description: "git clean with force and dry-run options", command: "git clean -f -n" },
  { description: "git clean help", command: "git clean --help" },
  { description: "git rm help", command: "git rm --help file" },
  { description: "rm help", command: "rm --help" },
  { description: "rm version output", command: "rm --version file" },
  { description: "xargs invoking rm help", command: "printf '%s\\0' file | xargs rm --help" },
  { description: "an uppercase command unrelated to rm", command: "RM obsolete.txt" },
  { description: "command substitution inside a shell comment", command: "echo safe # $(rm obsolete.txt)" },
  {
    description: "rm text inside a quoted heredoc",
    command: "cat <<'EOF'\nrm obsolete.txt\nEOF",
  },
  { description: "-delete passed as a find -exec argument", command: "find . -exec echo -delete \\;" },
  { description: "command -v looking up multiple names", command: "command -v rm obsolete.txt" },
  { description: "env help followed by command-like operands", command: "env --help rm obsolete.txt" },
  { description: "shred help with removal-looking options", command: "shred -u --help obsolete.txt" },
  {
    description: "-c passed as an argument to a shell script",
    command: "bash safe-script.sh -c 'rm obsolete.txt'",
  },
] as const;

for (const { description, command } of nonDeletionCommandCases) {
  test(`does not classify ${description} as file deletion`, () => {
    assert.equal(isFileDeletionCommand(command), false);
  });
}
