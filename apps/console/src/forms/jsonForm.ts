export type JsonObject = Record<string, unknown>;

export type JsonParseFailure = {
  ok: false;
  message: string;
  line: number;
  column: number;
};

export type JsonParseResult = JsonObject | JsonParseFailure;

export type JsonEditorState = {
  lastValidValue?: JsonObject;
  error?: JsonParseFailure | null;
};

export function parseJsonObject(text: string): JsonParseResult {
  try {
    const parsed = JSON.parse(text) as unknown;
    if (!isJsonObject(parsed)) {
      return {
        ok: false,
        message: "JSON must be an object.",
        line: 1,
        column: 1,
      };
    }
    return parsed;
  } catch (caught) {
    const location = locateJsonError(text, caught);
    return {
      ok: false,
      message: `Invalid JSON: ${caught instanceof Error ? caught.message : String(caught)}`,
      ...location,
    };
  }
}

export function updateJsonText(state: JsonEditorState, text: string): Required<JsonEditorState> {
  const parsed = parseJsonObject(text);
  if (isJsonParseFailure(parsed)) {
    return {
      lastValidValue: state.lastValidValue ?? {},
      error: parsed,
    };
  }
  return {
    lastValidValue: parsed,
    error: null,
  };
}

export function isJsonParseFailure(value: JsonParseResult): value is JsonParseFailure {
  return Boolean(value && typeof value === "object" && "ok" in value && value.ok === false);
}

function locateJsonError(text: string, error: unknown): { line: number; column: number } {
  const message = error instanceof Error ? error.message : "";
  const match = message.match(/position\s+(\d+)/i);
  const position = match ? Number(match[1]) : text.length;
  const before = text.slice(0, Math.max(0, position));
  const lines = before.split(/\r?\n/);
  return {
    line: lines.length,
    column: lines[lines.length - 1].length + 1,
  };
}

function isJsonObject(value: unknown): value is JsonObject {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}
