import { describe, expect, it } from "vitest";
import { buildExtractiveAnswer, finalizeAnswer } from "@/lib/answer";
import {
  ENGLISH_CITATION_PATTERN,
  enforceCitations,
  extractCitations,
  formatCitation,
  validateCitations,
} from "@/lib/citations";
import { getCorpus } from "@/lib/corpus";
import { ungroundedMessage } from "@/lib/prompts";
import { retrieveGroundedSections } from "@/lib/rag";

describe("citation format", () => {
  it("formats the mandatory English [Act Title, Section (Dafa) Number] pattern", () => {
    const citation = formatCitation("National Civil Code, 2074", "70", "en");
    expect(citation).toBe("[National Civil Code, 2074, Section (Dafa) 70]");
    expect(citation).toMatch(ENGLISH_CITATION_PATTERN);
  });

  it("formats the Devanagari दफा form", () => {
    expect(formatCitation("राष्ट्रिय देवानी संहिता, २०७४", "70", "ne")).toBe(
      "[राष्ट्रिय देवानी संहिता, २०७४, दफा ७०]",
    );
  });

  it("extracts bilingual citations from a mixed answer", () => {
    const text =
      "Marriage age is twenty [National Civil Code, 2074, Section (Dafa) 70] र [राष्ट्रिय देवानी संहिता, २०७४, दफा ७०]।";
    const citations = extractCitations(text);
    expect(citations).toHaveLength(2);
    expect(citations[0]?.sectionNumber).toBe("70");
    expect(citations[1]?.language).toBe("ne");
  });

  it("accepts only citations that exist in the allowed corpus", () => {
    const corpus = getCorpus();
    const text =
      "Dignity [Constitution of Nepal, Section (Dafa) 16] invented [Imaginary Act, Section (Dafa) 999]";
    const citations = validateCitations(text, corpus);
    expect(citations.find((item) => item.sectionNumber === "16")?.valid).toBe(true);
    expect(citations.find((item) => item.sectionNumber === "999")?.valid).toBe(false);
  });

  it("refuses ungrounded legal claims and strips invented dafa numbers", () => {
    const result = enforceCitations(
      "You may marry at sixteen [Imaginary Act, Section (Dafa) 12]",
      getCorpus(),
      "en",
      ungroundedMessage("en"),
    );
    expect(result.grounded).toBe(false);
    expect(result.answer).toBe(ungroundedMessage("en"));
    expect(result.citations).toHaveLength(0);
  });

  it("repairs loose Article/दफा mentions into the required citation form", () => {
    const marriage = getCorpus().filter((section) => section.id === "civil-70");
    const result = enforceCitations(
      "The Civil Code says section 70 both must be twenty.",
      marriage,
      "en",
      ungroundedMessage("en"),
    );
    expect(result.grounded).toBe(true);
    expect(result.answer).toContain("[National Civil Code, 2074, Section (Dafa) 70]");
  });
});

describe("extractive RAG answers", () => {
  it("answers marriage age with a Civil Code dafa citation", () => {
    const sources = retrieveGroundedSections("minimum marriage age in Nepal", 5, "en");
    const draft = buildExtractiveAnswer("minimum marriage age in Nepal", sources, "en");
    const final = finalizeAnswer(draft.answer, sources, "en");
    expect(final.grounded).toBe(true);
    expect(final.answer).toMatch(/\[National Civil Code, 2074, Section \(Dafa\) 70\]/);
    expect(sources.some((section) => section.id === "civil-70")).toBe(true);
  });

  it("answers a Nepali labour question in Devanagari with दफा citations", () => {
    const sources = retrieveGroundedSections("एक हप्तामा कति घण्टा काम", 5, "ne");
    const draft = buildExtractiveAnswer("एक हप्तामा कति घण्टा काम", sources, "ne");
    const final = finalizeAnswer(draft.answer, sources, "ne");
    expect(final.grounded).toBe(true);
    expect(final.answer).toMatch(/दफा/);
    expect(sources.some((section) => section.id === "labour-28")).toBe(true);
  });
});
