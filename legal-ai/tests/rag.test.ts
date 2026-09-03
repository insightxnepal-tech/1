import { describe, expect, it } from "vitest";
import { retrieveGroundedSections, retrieveSections, tokenize } from "@/lib/rag";

describe("retrieval", () => {
  it("ranks Constitution Article 16 for death-penalty questions", () => {
    const results = retrieveGroundedSections("Does Nepal allow the death penalty?", 5, "en");
    expect(results[0]?.id).toBe("const-16");
  });

  it("finds Companies Act incorporation rules", () => {
    const results = retrieveSections("public company seven promoters", 5, "en");
    expect(results.some((section) => section.id === "company-3")).toBe(true);
  });

  it("keeps Devanagari matras attached when tokenizing", () => {
    const tokens = tokenize("नेपालमा विवाहको न्यूनतम उमेर कति हो?");
    expect(tokens).toEqual(expect.arrayContaining(["विवाह", "न्यूनतम", "उमेर"]));
    expect(tokens).not.toContain("नेपाल");
  });

  it("returns nothing useful for empty queries", () => {
    expect(retrieveSections("   ", 5, "en")).toEqual([]);
  });

  it("ranks Civil Code दफा ७० for a Nepali marriage-age question", () => {
    const results = retrieveGroundedSections(
      "नेपालमा विवाहको न्यूनतम उमेर कति हो?",
      5,
      "ne",
    );
    expect(results[0]?.id).toBe("civil-70");
  });

  it("ranks Labour Act दफा २८ for a Nepali working-hours question", () => {
    const results = retrieveGroundedSections("नेपालमा दैनिक कामको समय कति हो?", 5, "ne");
    expect(results[0]?.id).toBe("labour-28");
  });

  it("does not ground unrelated questions", () => {
    expect(
      retrieveGroundedSections("What is the tax rate for importing mangoes from Mars?", 5, "en"),
    ).toEqual([]);
  });
});
