import type { ChatMessage, ChatRequest, LanguagePreference } from "./types";

function isLanguagePreference(value: unknown): value is LanguagePreference {
  return value === "en" || value === "ne" || value === "auto" || value === undefined;
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (typeof value !== "object" || value === null) return false;
  const record = value as { role?: unknown; content?: unknown };
  return (
    (record.role === "user" || record.role === "assistant") &&
    typeof record.content === "string"
  );
}

export function parseChatRequest(payload: unknown): ChatRequest | { error: string } {
  if (typeof payload !== "object" || payload === null) {
    return { error: "Request body must be a JSON object." };
  }

  const record = payload as { messages?: unknown; language?: unknown };
  if (!Array.isArray(record.messages) || record.messages.length === 0) {
    return { error: "messages must be a non-empty array." };
  }
  if (!record.messages.every(isChatMessage)) {
    return { error: "Each message must have role 'user' | 'assistant' and string content." };
  }
  if (!isLanguagePreference(record.language)) {
    return { error: "language must be 'en', 'ne', or 'auto'." };
  }

  return {
    messages: record.messages,
    language: record.language,
  };
}

export function parseSearchQuery(url: URL): { query: string; language: LanguagePreference; limit: number } | { error: string } {
  const query = url.searchParams.get("q")?.trim() ?? "";
  if (!query) {
    return { error: "Query parameter q is required." };
  }

  const languageRaw = url.searchParams.get("language") ?? "auto";
  if (languageRaw !== "en" && languageRaw !== "ne" && languageRaw !== "auto") {
    return { error: "language must be 'en', 'ne', or 'auto'." };
  }

  const limitRaw = url.searchParams.get("limit");
  const limit = limitRaw ? Number.parseInt(limitRaw, 10) : 8;
  if (!Number.isFinite(limit) || limit < 1 || limit > 20) {
    return { error: "limit must be an integer between 1 and 20." };
  }

  return { query, language: languageRaw, limit };
}
