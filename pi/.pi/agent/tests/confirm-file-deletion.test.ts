import assert from "node:assert/strict";
import test from "node:test";

import confirmFileDeletionExtension from "../extensions/confirm-file-deletion.ts";

type EventHandler = (event: unknown, context: unknown) => Promise<unknown>;
type ConfirmationOptions = { timeout?: number };
type ConfirmationFunction = (
  title: string,
  message: string,
  options?: ConfirmationOptions,
) => Promise<boolean>;

function registeredEventHandler(eventName: string): EventHandler {
  const handlers = new Map<string, EventHandler>();
  confirmFileDeletionExtension({
    on(registeredEventName: string, handler: EventHandler) {
      handlers.set(registeredEventName, handler);
    },
  } as never);

  const handler = handlers.get(eventName);
  assert.ok(handler, `${eventName} handler was not registered`);
  return handler;
}

function interactiveContext(confirm: ConfirmationFunction) {
  return {
    hasUI: true,
    mode: "tui",
    ui: { confirm },
  };
}

function assertToolCallWasBlocked(result: unknown, expectedReason: string): void {
  assert.ok(result !== null && typeof result === "object");
  const blockedResult = result as { block?: unknown; reason?: unknown };
  assert.equal(blockedResult.block, true);
  assert.equal(blockedResult.reason, expectedReason);
}

function assertUserBashWasBlocked(result: unknown, expectedOutput: string): void {
  assert.ok(result !== null && typeof result === "object");
  const replacement = (result as { result?: unknown }).result;
  assert.ok(replacement !== null && typeof replacement === "object");

  const bashResult = replacement as {
    output?: unknown;
    exitCode?: unknown;
    cancelled?: unknown;
    truncated?: unknown;
  };
  assert.equal(bashResult.output, expectedOutput);
  assert.equal(typeof bashResult.exitCode, "number");
  assert.notEqual(bashResult.exitCode, 0);
  assert.equal(bashResult.cancelled, false);
  assert.equal(bashResult.truncated, false);
}

test("allows an agent deletion command after explicit confirmation", async () => {
  const toolCallHandler = registeredEventHandler("tool_call");
  const command = "rm obsolete.txt";
  let promptCount = 0;
  let displayedTitle = "";
  let displayedMessage = "";

  const result = await toolCallHandler(
    { toolName: "bash", input: { command } },
    interactiveContext(async (title, message) => {
      promptCount += 1;
      displayedTitle = title;
      displayedMessage = message;
      return true;
    }),
  );

  assert.equal(result, undefined);
  assert.equal(promptCount, 1);
  assert.match(displayedTitle, /delete/i);
  assert.ok(displayedMessage.includes(command));
});

test("blocks an agent deletion command when confirmation is declined", async () => {
  const toolCallHandler = registeredEventHandler("tool_call");

  const result = await toolCallHandler(
    { toolName: "bash", input: { command: "rm obsolete.txt" } },
    interactiveContext(async () => false),
  );

  assertToolCallWasBlocked(result, "File deletion declined by user");
});

test("does not prompt for a non-deleting agent bash command", async () => {
  const toolCallHandler = registeredEventHandler("tool_call");
  let promptCount = 0;

  const result = await toolCallHandler(
    { toolName: "bash", input: { command: "printf 'safe\\n'" } },
    interactiveContext(async () => {
      promptCount += 1;
      return true;
    }),
  );

  assert.equal(result, undefined);
  assert.equal(promptCount, 0);
});

test("does not inspect command-shaped input from non-bash tools", async () => {
  const toolCallHandler = registeredEventHandler("tool_call");
  let promptCount = 0;

  const result = await toolCallHandler(
    { toolName: "custom_tool", input: { command: "rm obsolete.txt" } },
    interactiveContext(async () => {
      promptCount += 1;
      return true;
    }),
  );

  assert.equal(result, undefined);
  assert.equal(promptCount, 0);
});

test("blocks an agent deletion command when Pi cannot prompt", async () => {
  const toolCallHandler = registeredEventHandler("tool_call");

  const result = await toolCallHandler(
    { toolName: "bash", input: { command: "rm obsolete.txt" } },
    {
      hasUI: false,
      mode: "print",
      ui: {
        confirm: async () => {
          throw new Error("confirmation must not be attempted without a UI");
        },
      },
    },
  );

  assertToolCallWasBlocked(result, "File deletion blocked because confirmation is unavailable");
});

test("blocks an agent deletion command when displaying confirmation fails", async () => {
  const toolCallHandler = registeredEventHandler("tool_call");

  const result = await toolCallHandler(
    { toolName: "bash", input: { command: "rm obsolete.txt" } },
    interactiveContext(async () => {
      throw new Error("UI failure");
    }),
  );

  assertToolCallWasBlocked(result, "File deletion blocked because confirmation failed");
});

test("adds a fail-closed timeout to RPC confirmation requests", async () => {
  const toolCallHandler = registeredEventHandler("tool_call");
  let receivedOptions: ConfirmationOptions | undefined;

  const result = await toolCallHandler(
    { toolName: "bash", input: { command: "rm obsolete.txt" } },
    {
      hasUI: true,
      mode: "rpc",
      ui: {
        confirm: async (_title: string, _message: string, options?: ConfirmationOptions) => {
          receivedOptions = options;
          return false;
        },
      },
    },
  );

  assertToolCallWasBlocked(result, "File deletion declined by user");
  assert.ok(receivedOptions, "RPC confirmation did not include options");
  assert.equal(typeof receivedOptions.timeout, "number");
  assert.ok(receivedOptions.timeout > 0, "RPC confirmation timeout must be positive");
});

test("allows a user deletion command after explicit confirmation", async () => {
  const userBashHandler = registeredEventHandler("user_bash");

  const result = await userBashHandler(
    { command: "rm obsolete.txt" },
    interactiveContext(async () => true),
  );

  assert.equal(result, undefined);
});

test("blocks a user deletion command when confirmation is declined", async () => {
  const userBashHandler = registeredEventHandler("user_bash");

  const result = await userBashHandler(
    { command: "rm obsolete.txt" },
    interactiveContext(async () => false),
  );

  assertUserBashWasBlocked(result, "File deletion declined by user.");
});

test("does not prompt for a non-deleting user bash command", async () => {
  const userBashHandler = registeredEventHandler("user_bash");
  let promptCount = 0;

  const result = await userBashHandler(
    { command: "printf 'safe\\n'" },
    interactiveContext(async () => {
      promptCount += 1;
      return true;
    }),
  );

  assert.equal(result, undefined);
  assert.equal(promptCount, 0);
});

test("blocks a user deletion command when Pi cannot prompt", async () => {
  const userBashHandler = registeredEventHandler("user_bash");

  const result = await userBashHandler(
    { command: "rm obsolete.txt" },
    {
      hasUI: false,
      mode: "print",
      ui: {
        confirm: async () => {
          throw new Error("confirmation must not be attempted without a UI");
        },
      },
    },
  );

  assertUserBashWasBlocked(result, "File deletion blocked because confirmation is unavailable.");
});

test("blocks a user deletion command when displaying confirmation fails", async () => {
  const userBashHandler = registeredEventHandler("user_bash");

  const result = await userBashHandler(
    { command: "rm obsolete.txt" },
    interactiveContext(async () => {
      throw new Error("UI failure");
    }),
  );

  assertUserBashWasBlocked(result, "File deletion blocked because confirmation failed.");
});
