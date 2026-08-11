import assert from "node:assert/strict";
import test from "node:test";

import { isDirectTemporaryDirectoryDeletion } from "../../extensions/confirm-file-deletion/temporary-directory-policy.ts";

for (const source of [
  "rm -rf /tmp/build-output",
  "rmdir -- /tmp/empty-directory",
  "/usr/bin/unlink /tmp/socket",
  "rm '/tmp/file with spaces' /tmp/second-file",
]) {
  test(`allows direct deletion of literal temporary-directory entries: ${source}`, () => {
    assert.equal(isDirectTemporaryDirectoryDeletion(source), true);
  });
}

for (const source of [
  "rm /tmp",
  "rm /tmp/",
  "rm /tmp/build-output /home/user/important-file",
  'rm "$TMPDIR/build-output"',
  "rm /tmp/*",
  "rm /tmp/{first,second}",
  "rm /tmp/link/../outside",
  "rm /tmp/link/",
  "command rm /tmp/build-output",
  "rm /tmp/build-output && rm /home/user/important-file",
  "rm /tmp/build-output >$(rm /home/user/important-file)",
  "find /tmp -delete",
  "rm -rf /tmp/build-output &",
]) {
  test(`requires confirmation outside the narrow temporary-directory exception: ${source}`, () => {
    assert.equal(isDirectTemporaryDirectoryDeletion(source), false);
  });
}
