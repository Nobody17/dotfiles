# Messages to the orchestrator

The orchestrator reads files, not your screen. Write each message for the orchestrator as a new file in `<run>/messages/`. `<run>` is the folder that holds the `handoffs/` folder of your handoff path. Create `messages/` if it is missing.

Name: `<handoff name>-<UTC time YYYYMMDDTHHMMSSZ>-<kind>.md`, for example `t07-20261106T153000Z-question.md` for the handoff `t07.md`.

Write the text to the same name with `.tmp` in place of `.md`, then rename it to `.md`. The orchestrator then reads only complete files. A sent message stays as it is; a correction is a new message.

| Kind | When | Content |
|---|---|---|
| `ready` | You read the assignment and verified the worktree and the starting SHA. | One line. |
| `question` | You need a decision of the orchestrator or the user. | The decision, the options, your recommendation. Then end your turn; the answer comes as a prompt. |
| `blocked` | You cannot continue. | The reason, and the state you leave: worktree, unfinished Git operation, running processes. |
| `status` | The orchestrator asked for your status. | The answer. |

The handoff file is your result, so it needs no message. After each message or handoff, end your reply with one line that names its path.
