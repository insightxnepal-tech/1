import { describe, expect, it } from "vitest";
import { parseChatRequest, parseSearchQuery } from "@/lib/http";

describe("typed request parsing", () => {
  it("accepts a well-formed chat body", () => {
    const parsed = parseChatRequest({
      messages: [{ role: "user", content: "marriage age" }],
      language: "auto",
    });
    expect(parsed).toEqual({
      messages: [{ role: "user", content: "marriage age" }],
      language: "auto",
    });
  });

  it("rejects malformed chat bodies", () => {
    expect(parseChatRequest({})).toEqual({ error: "messages must be a non-empty array." });
    expect(parseChatRequest({ messages: [{ role: "system", content: "x" }] })).toEqual({
      error: "Each message must have role 'user' | 'assistant' and string content.",
    });
  });

  it("parses search query parameters", () => {
    const ok = parseSearchQuery(new URL("https://nyaya.test/api/search?q=labour&language=ne"));
    expect(ok).toEqual({ query: "labour", language: "ne", limit: 8 });
    const bad = parseSearchQuery(new URL("https://nyaya.test/api/search"));
    expect(bad).toEqual({ error: "Query parameter q is required." });
  });
});
