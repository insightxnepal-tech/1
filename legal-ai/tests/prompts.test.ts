import { describe, expect, it } from "vitest";
import { buildSystemPrompt, buildUserPrompt, CITATION_RULE_EN } from "@/lib/prompts";
import { retrieveGroundedSections } from "@/lib/rag";

describe("RAG system prompts", () => {
  it("always forces the strict English citation format", () => {
    const english = buildSystemPrompt("en");
    const nepali = buildSystemPrompt("ne");
    expect(CITATION_RULE_EN).toContain("[Act Title, Section (Dafa) Number]");
    expect(english).toContain("[Act Title, Section (Dafa) Number]");
    expect(nepali).toContain("[Act Title, Section (Dafa) Number]");
    expect(english).toContain("Never invent");
    expect(nepali).toContain("दफा");
  });

  it("embeds retrieved bilingual excerpts for grounding", () => {
    const sources = retrieveGroundedSections("right to equality", 3, "en");
    const prompt = buildUserPrompt("right to equality", sources, "en");
    expect(prompt).toContain("[Constitution of Nepal, Section (Dafa) 18]");
    expect(prompt).toContain("नेपाली:");
    expect(prompt).toContain("समानता");
  });
});
