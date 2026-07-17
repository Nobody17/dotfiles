import assert from "node:assert/strict";
import test from "node:test";

import confirmFileDeletionExtension from "../../extensions/confirm-file-deletion/index.ts";

type EventHandler = (event: any, context: any) => Promise<unknown>;
type SelectFunction = (prompt: string, options: string[]) => Promise<string | undefined>;

function registeredEventHandler(eventName: "tool_call" | "user_bash"): EventHandler {
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

function tuiContext(select: SelectFunction) {
  return { hasUI: true, mode: "tui", ui: { select } };
}

function assertToolCallBlocked(result: unknown, reason: string): void {
  assert.deepEqual(result, { block: true, reason });
}

function assertUserBashBlocked(result: unknown, output: string): void {
  assert.deepEqual(result, {
    result: { output, exitCode: 1, cancelled: false, truncated: false },
  });
}

test("allows agent Bash only after an exact affirmative selection", async () => {
  const handler = registeredEventHandler("tool_call");
  let receivedPrompt = "";
  let receivedOptions: string[] = [];

  const result = await handler(
    { toolName: "bash", input: { command: "rm obsolete.txt" } },
    tuiContext(async (prompt, options) => {
      receivedPrompt = prompt;
      receivedOptions = options;
      return "Yes, allow deletion";
    }),
  );

  assert.equal(result, undefined);
  assert.deepEqual(receivedOptions, ["No, block it", "Yes, allow deletion"]);
  assert.match(receivedPrompt, /rm obsolete\.txt/);
  assert.match(receivedPrompt, /direct/i);
});

for (const choice of [undefined, "No, block it", "yes", "unexpected value"]) {
  test(`blocks agent Bash when selector returns ${String(choice)}`, async () => {
    const handler = registeredEventHandler("tool_call");

    const result = await handler(
      { toolName: "bash", input: { command: "rm obsolete.txt" } },
      tuiContext(async () => choice),
    );

    assertToolCallBlocked(result, "File deletion declined by user");
  });
}

test("blocks agent Bash if selection throws", async () => {
  const handler = registeredEventHandler("tool_call");

  const result = await handler(
    { toolName: "bash", input: { command: "rm obsolete.txt" } },
    tuiContext(async () => {
      throw new Error("UI failed");
    }),
  );

  assertToolCallBlocked(result, "File deletion blocked because confirmation failed");
});

test("blocks user Bash after a declined selection", async () => {
  const handler = registeredEventHandler("user_bash");

  const result = await handler(
    { command: "rm obsolete.txt" },
    tuiContext(async () => "No, block it"),
  );

  assertUserBashBlocked(result, "File deletion declined by user.");
});

test("allows user Bash after an exact affirmative selection", async () => {
  const handler = registeredEventHandler("user_bash");

  const result = await handler(
    { command: "rm obsolete.txt" },
    tuiContext(async () => "Yes, allow deletion"),
  );

  assert.equal(result, undefined);
});

for (const mode of ["rpc", "json", "print"] as const) {
  test(`blocks agent Bash in ${mode} without selecting`, async () => {
    const handler = registeredEventHandler("tool_call");
    let selectCalls = 0;

    const result = await handler(
      { toolName: "bash", input: { command: "rm obsolete.txt" } },
      {
        hasUI: mode === "rpc",
        mode,
        ui: {
          select: async () => {
            selectCalls += 1;
            return "Yes, allow deletion";
          },
        },
      },
    );

    assert.equal(selectCalls, 0);
    assertToolCallBlocked(result, "File deletion blocked because confirmation is unavailable");
  });
}

test("blocks TUI execution when the UI is unavailable", async () => {
  const handler = registeredEventHandler("user_bash");

  const result = await handler(
    { command: "rm obsolete.txt" },
    { hasUI: false, mode: "tui", ui: { select: async () => "Yes, allow deletion" } },
  );

  assertUserBashBlocked(result, "File deletion blocked because confirmation is unavailable.");
});

for (const mode of ["rpc", "json", "print"] as const) {
  test(`blocks user Bash in ${mode} without selecting`, async () => {
    const handler = registeredEventHandler("user_bash");
    let selectCalls = 0;

    const result = await handler(
      { command: "rm obsolete.txt" },
      {
        hasUI: mode === "rpc",
        mode,
        ui: {
          select: async () => {
            selectCalls += 1;
            return "Yes, allow deletion";
          },
        },
      },
    );

    assert.equal(selectCalls, 0);
    assertUserBashBlocked(result, "File deletion blocked because confirmation is unavailable.");
  });
}

test("blocks user Bash if selection throws", async () => {
  const handler = registeredEventHandler("user_bash");

  const result = await handler(
    { command: "rm obsolete.txt" },
    tuiContext(async () => {
      throw new Error("UI failed");
    }),
  );

  assertUserBashBlocked(result, "File deletion blocked because confirmation failed.");
});

test("does not prompt for safe Bash or unrelated tools", async () => {
  const handler = registeredEventHandler("tool_call");
  let selectCalls = 0;
  const context = tuiContext(async () => {
    selectCalls += 1;
    return "Yes, allow deletion";
  });

  const safeResult = await handler({ toolName: "bash", input: { command: "printf safe" } }, context);
  const otherToolResult = await handler({ toolName: "read", input: { command: "rm obsolete.txt" } }, context);

  assert.equal(safeResult, undefined);
  assert.equal(otherToolResult, undefined);
  assert.equal(selectCalls, 0);
});

test("does not prompt for safe user Bash", async () => {
  const handler = registeredEventHandler("user_bash");
  let selectCalls = 0;

  const result = await handler(
    { command: "printf safe" },
    tuiContext(async () => {
      selectCalls += 1;
      return "Yes, allow deletion";
    }),
  );

  assert.equal(result, undefined);
  assert.equal(selectCalls, 0);
});

test("prompts for unknown commands and includes their finding", async () => {
  const handler = registeredEventHandler("tool_call");
  let prompt = "";

  const result = await handler(
    { toolName: "bash", input: { command: "\"$deleter\" obsolete.txt" } },
    tuiContext(async (value) => {
      prompt = value;
      return "Yes, allow deletion";
    }),
  );

  assert.equal(result, undefined);
  assert.match(prompt, /dynamic command/i);
});
