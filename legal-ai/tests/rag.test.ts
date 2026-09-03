import { describe, expect, it } from "vitest";
import { retrieveGroundedSections, retrieveSections } from "@/lib/rag";

describe("retrieval", () => {
  it("ranks Constitution Article 16 for death-penalty questions", () => {
    const results = retrieveGroundedSections("Does Nepal allow the death penalty?", 5, "en");
    expect(results[0]?.id).toBe("const-16");
  });

  it("finds Companies Act incorporation rules", () => {
    const results = retrieveSections("public company seven promoters", 5, "en");
    expect(results.some((section) => section.id === "company-3")).toBe(true);
  });

  it("returns nothing useful for empty queries", () => {
    expect(retrieveSections("   ", 5, "en")).toEqual([]);
  });
});
