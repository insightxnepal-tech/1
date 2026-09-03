import { getCorpus } from "./corpus";
import { detectLanguage, toAsciiDigits } from "./language";
import type { CorpusSection, Language, RetrievedSection } from "./types";

const STOP_WORDS = new Set([
  "a",
  "an",
  "the",
  "and",
  "or",
  "of",
  "to",
  "in",
  "for",
  "on",
  "is",
  "are",
  "what",
  "does",
  "how",
  "can",
  "under",
  "nepal",
  "nepali",
  "law",
  "please",
  "tell",
  "about",
  "के",
  "हो",
  "छ",
  "मा",
  "को",
  "का",
  "की",
  "र",
  "नेपाल",
  "नेपाली",
]);

function tokenize(text: string): string[] {
  const ascii = toAsciiDigits(text.toLowerCase());
  return ascii
    .split(/[^\p{L}\p{N}]+/u)
    .map((token) => token.trim())
    .filter((token) => token.length >= 2 && !STOP_WORDS.has(token));
}

function scoreSection(
  tokens: readonly string[],
  language: Language,
  section: CorpusSection,
): number {
  const haystack = [
    section.actTitleEn,
    section.actTitleNe,
    section.headingEn,
    section.headingNe,
    section.textEn,
    section.textNe,
    section.tags.join(" "),
    `section ${section.sectionNumber}`,
    `dafa ${section.sectionNumber}`,
    `दफा ${section.sectionNumber}`,
    `धारा ${section.sectionNumber}`,
  ]
    .join(" ")
    .toLowerCase();

  const queryText = tokens.join(" ");
  let score = 0;
  for (const tag of section.tags) {
    const normalized = tag.toLowerCase();
    if (normalized.includes(" ") && queryText.includes(normalized)) {
      score += 5;
    }
  }
  for (const token of tokens) {
    if (!haystack.includes(token)) continue;
    score += section.tags.some((tag) => tag.toLowerCase() === token) ? 3 : 1;
    if (section.headingEn.toLowerCase().includes(token)) score += 2;
    if (section.headingNe.toLowerCase().includes(token)) score += 2;
  }

  if (language === "ne") {
    score += 0.15;
  }

  return score;
}

export function retrieveSections(
  query: string,
  limit = 5,
  language: Language = detectLanguage(query),
): RetrievedSection[] {
  const tokens = tokenize(query);
  if (tokens.length === 0) {
    return [];
  }

  return getCorpus()
    .map((section) => ({
      ...section,
      score: scoreSection(tokens, language, section),
    }))
    .filter((section) => section.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, limit);
}

export const MINIMUM_RETRIEVAL_SCORE = 2;

export function retrieveGroundedSections(
  query: string,
  limit = 5,
  language: Language = detectLanguage(query),
): RetrievedSection[] {
  return retrieveSections(query, limit, language).filter(
    (section) => section.score >= MINIMUM_RETRIEVAL_SCORE,
  );
}
