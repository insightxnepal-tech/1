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
  "was",
  "were",
  "be",
  "been",
  "being",
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
  "from",
  "with",
  "that",
  "this",
  "shall",
  "have",
  "has",
  "had",
  "any",
  "may",
  "not",
  "by",
  "as",
  "at",
  "it",
  "if",
  "you",
  "your",
  "will",
  "would",
  "which",
  "their",
  "them",
  "they",
  "who",
  "when",
  "where",
  "than",
  "also",
  "into",
  "such",
  "other",
  "more",
  "only",
  "over",
  "after",
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
  "कति",
  "गर्ने",
  "लागि",
  "यो",
  "त्यो",
  "कुनै",
  "पनि",
]);

const NEPALI_SUFFIXES = [
  "हरूलाई",
  "हरूको",
  "हरू",
  "लाई",
  "बाट",
  "सँग",
  "देखि",
  "पछि",
  "को",
  "का",
  "की",
  "मा",
  "ले",
  "ने",
];

function morphologicalVariants(token: string): string[] {
  const variants = new Set([token]);
  for (const suffix of NEPALI_SUFFIXES) {
    if (token.length > suffix.length + 1 && token.endsWith(suffix)) {
      variants.add(token.slice(0, -suffix.length));
    }
  }
  return [...variants];
}

export function tokenize(text: string): string[] {
  const ascii = toAsciiDigits(text.toLowerCase());
  const raw = ascii
    .split(/[^\p{L}\p{N}\p{M}]+/u)
    .map((token) => token.trim())
    .filter(Boolean);

  const tokens = new Set<string>();
  for (const token of raw) {
    for (const variant of morphologicalVariants(token)) {
      if (variant.length >= 2 && !STOP_WORDS.has(variant)) {
        tokens.add(variant);
      }
    }
  }
  return [...tokens];
}

function scoreSection(query: string, tokens: readonly string[], section: CorpusSection): number {
  const queryNorm = toAsciiDigits(query.toLowerCase());
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

  let score = 0;
  for (const tag of section.tags) {
    const normalized = tag.toLowerCase();
    if (normalized.includes(" ")) {
      if (queryNorm.includes(normalized)) score += 10;
      continue;
    }
    if (tokens.includes(normalized)) {
      score += 4;
    }
  }

  for (const token of tokens) {
    if (!haystack.includes(token)) continue;
    score += section.tags.some((tag) => tag.toLowerCase() === token) ? 3 : 1;
    if (section.headingEn.toLowerCase().includes(token)) score += 2;
    if (section.headingNe.toLowerCase().includes(token)) score += 2;
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

  void language;

  return getCorpus()
    .map((section) => ({
      ...section,
      score: scoreSection(query, tokens, section),
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
