import { describe, expect, it } from "vitest";
import {
  detectLanguage,
  normalizeSectionNumber,
  resolveLanguage,
  toAsciiDigits,
  toDevanagariDigits,
} from "@/lib/language";

describe("bilingual language helpers", () => {
  it("detects Devanagari as Nepali", () => {
    expect(detectLanguage("विवाहको उमेर कति हो?")).toBe("ne");
    expect(detectLanguage("What is the marriage age?")).toBe("en");
  });

  it("honours an explicit language override", () => {
    expect(resolveLanguage("en", "विवाह")).toBe("en");
    expect(resolveLanguage("auto", "विवाह")).toBe("ne");
  });

  it("round-trips section numbers between scripts", () => {
    expect(toDevanagariDigits("70")).toBe("७०");
    expect(toAsciiDigits("दफा ७०")).toBe("दफा 70");
    expect(normalizeSectionNumber("०१६")).toBe("16");
  });
});
