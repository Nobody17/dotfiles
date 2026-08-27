import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// Local llama.cpp server (llama-swap) at 127.0.0.1:8080.
// Every model the server reports via /v1/models is registered, so any
// locally running model appears in the model list (Ctrl+P / Ctrl+L).
const BASE_URL = "http://127.0.0.1:8080/v1";
const PROBE_TIMEOUT_MS = 2000;
const DEFAULT_CONTEXT_WINDOW = 32768;
const DEFAULT_MAX_TOKENS = 8192;

const defaultCompat = {
  supportsDeveloperRole: false,
  supportsReasoningEffort: false,
  supportsStrictMode: false,
  maxTokensField: "max_tokens",
};

// Per-model overrides for models that need non-default settings.
// Everything else uses the safe defaults above.
const modelOverrides: Record<
  string,
  {
    name?: string;
    reasoning?: boolean;
    thinkingLevelMap?: Record<string, string | null>;
    input?: ("text" | "image")[];
    contextWindow?: number;
    maxTokens?: number;
    compat?: Record<string, unknown>;
  }
> = {
  goetia: {
    name: "Goetia 26B Q4",
    reasoning: true,
    thinkingLevelMap: {
      minimal: null,
      low: null,
      medium: null,
      high: "high",
    },
    contextWindow: 49152,
    maxTokens: 8192,
    compat: {
      ...defaultCompat,
      thinkingFormat: "chat-template",
      chatTemplateKwargs: {
        enable_thinking: { $var: "thinking.enabled" },
      },
    },
  },
};

interface ServerModel {
  id: string;
  meta?: {
    n_ctx?: number;
    n_ctx_train?: number;
  };
}

async function fetchServerModels(): Promise<ServerModel[] | null> {
  try {
    const response = await fetch(`${BASE_URL}/models`, {
      signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
    });
    if (!response.ok) return null;
    const payload = (await response.json()) as { data?: ServerModel[] };
    return Array.isArray(payload?.data) ? payload.data : null;
  } catch {
    return null;
  }
}

export default async function (pi: ExtensionAPI) {
  const serverModels = await fetchServerModels();
  if (!serverModels || serverModels.length === 0) return;

  const models = serverModels.map((serverModel) => {
    const override = modelOverrides[serverModel.id] ?? {};
    const contextWindow =
      override.contextWindow ??
      serverModel.meta?.n_ctx ??
      serverModel.meta?.n_ctx_train ??
      DEFAULT_CONTEXT_WINDOW;

    return {
      id: serverModel.id,
      name: override.name ?? serverModel.id,
      reasoning: override.reasoning ?? false,
      thinkingLevelMap: override.thinkingLevelMap,
      input: override.input ?? ["text"],
      contextWindow,
      maxTokens: override.maxTokens ?? DEFAULT_MAX_TOKENS,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      compat: override.compat ?? defaultCompat,
    };
  });

  pi.registerProvider("llama-local", {
    name: "llama.cpp (local)",
    baseUrl: BASE_URL,
    apiKey: "local",
    api: "openai-completions",
    models,
  });
}
