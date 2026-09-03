import { normalizeSectionNumber, toDevanagariDigits } from "./language";
import type { Citation, CorpusSection, Language } from "./types";

/** Canonical English form required by the architecture rule. */
export const ENGLISH_CITATION_PATTERN =
  /\[([^[\]]+),\s*Section \(Dafa\)\s+([0-9]+[A-Za-z0-9.\-]*)\]/g;

/** Bilingual Devanagari form: [ऐनको नाम, दफा नम्बर] */
export const NEPALI_CITATION_PATTERN =
  /\[([^[\]]+),\s*दफा\s+([०-९0-9]+[A-Za-z0-9.\-]*)\]/g;

export function formatCitation(
  actTitle: string,
  sectionNumber: string,
  language: Language = "en",
): string {
  if (language === "ne") {
    return `[${actTitle}, दफा ${toDevanagariDigits(sectionNumber)}]`;
  }
  return `[${actTitle}, Section (Dafa) ${sectionNumber}]`;
}

export function bilingualCitationPair(section: CorpusSection): {
  en: string;
  ne: string;
} {
  return {
    en: formatCitation(section.actTitleEn, section.sectionNumber, "en"),
    ne: formatCitation(section.actTitleNe, section.sectionNumber, "ne"),
  };
}

export function extractCitations(text: string): Citation[] {
  const found: Citation[] = [];
  const seen = new Set<string>();

  for (const match of text.matchAll(new RegExp(ENGLISH_CITATION_PATTERN.source, "g"))) {
    const raw = match[0];
    if (seen.has(raw)) continue;
    seen.add(raw);
    found.push({
      actTitle: match[1].trim(),
      sectionNumber: normalizeSectionNumber(match[2]),
      raw,
      language: "en",
      valid: false,
    });
  }

  for (const match of text.matchAll(new RegExp(NEPALI_CITATION_PATTERN.source, "g"))) {
    const raw = match[0];
    if (seen.has(raw)) continue;
    seen.add(raw);
    found.push({
      actTitle: match[1].trim(),
      sectionNumber: normalizeSectionNumber(match[2]),
      raw,
      language: "ne",
      valid: false,
    });
  }

  return found;
}

function normalizeTitle(title: string): string {
  return title
    .toLowerCase()
    .replace(/[।,.]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function titlesCompatible(citationTitle: string, section: CorpusSection): boolean {
  const cited = normalizeTitle(citationTitle);
  const en = normalizeTitle(section.actTitleEn);
  const ne = normalizeTitle(section.actTitleNe);
  return (
    cited === en ||
    cited === ne ||
    en.includes(cited) ||
    ne.includes(cited) ||
    cited.includes(en) ||
    cited.includes(ne)
  );
}

export function matchCitation(
  citation: Omit<Citation, "valid" | "matchedSectionId">,
  sections: readonly CorpusSection[],
): CorpusSection | undefined {
  const sectionNo = normalizeSectionNumber(citation.sectionNumber);
  return sections.find(
    (section) =>
      normalizeSectionNumber(section.sectionNumber) === sectionNo &&
      titlesCompatible(citation.actTitle, section),
  );
}

export function validateCitations(
  text: string,
  allowedSections: readonly CorpusSection[],
): Citation[] {
  return extractCitations(text).map((citation) => {
    const matched = matchCitation(citation, allowedSections);
    return {
      ...citation,
      valid: Boolean(matched),
      matchedSectionId: matched?.id,
    };
  });
}

const LOOSE_ARTICLE_RE =
  /\b(?:article|section|dafa|धारा|दफा)\s*[:.]?\s*([0-9०-९]+[A-Za-z0-9.\-]*)/gi;

export function repairLooseStatutoryMentions(
  text: string,
  sections: readonly CorpusSection[],
  language: Language,
): string {
  if (extractCitations(text).length > 0) {
    return text;
  }

  let repaired = text;
  const mentioned = new Set<string>();

  for (const match of text.matchAll(LOOSE_ARTICLE_RE)) {
    const sectionNo = normalizeSectionNumber(match[1]);
    const section = sections.find(
      (item) => normalizeSectionNumber(item.sectionNumber) === sectionNo,
    );
    if (!section) continue;
    const citation = formatCitation(
      language === "ne" ? section.actTitleNe : section.actTitleEn,
      section.sectionNumber,
      language,
    );
    if (mentioned.has(citation)) continue;
    mentioned.add(citation);
    repaired = repaired.replace(match[0], `${match[0]} ${citation}`);
  }

  return repaired;
}

export function stripInvalidCitations(text: string, citations: readonly Citation[]): string {
  let next = text;
  for (const citation of citations) {
    if (!citation.valid) {
      next = next.replaceAll(citation.raw, "").replace(/\s{2,}/g, " ");
    }
  }
  return next.trim();
}

export function hasLegalClaim(text: string): boolean {
  return /(section|dafa|act|code|constitution|ऐन|संहिता|संविधान|दफा|धारा|right|अधिकार)/i.test(
    text,
  );
}

export type CitationEnforcementResult = {
  answer: string;
  citations: Citation[];
  grounded: boolean;
  warnings: string[];
};

export function enforceCitations(
  answer: string,
  allowedSections: readonly CorpusSection[],
  language: Language,
  ungroundedMessage: string,
): CitationEnforcementResult {
  const warnings: string[] = [];
  const repaired = repairLooseStatutoryMentions(answer, allowedSections, language);
  const citations = validateCitations(repaired, allowedSections);
  const invalid = citations.filter((citation) => !citation.valid);
  const valid = citations.filter((citation) => citation.valid);

  let next = stripInvalidCitations(repaired, citations);

  if (invalid.length > 0) {
    warnings.push(
      language === "ne"
        ? "संग्रहमा नभएका उद्धरण हटाइयो।"
        : "Removed citations that are not in the retrieved corpus.",
    );
  }

  if (valid.length === 0) {
    return {
      answer: ungroundedMessage,
      citations: [],
      grounded: false,
      warnings: [
        ...warnings,
        language === "ne"
          ? "आधारभूत दफा बिना कानुनी दाबी स्वीकार गरिएन।"
          : "Refused to keep a legal claim without a grounded [Act Title, Section (Dafa) Number] citation.",
      ],
    };
  }

  if (hasLegalClaim(next) && valid.length === 0) {
    return {
      answer: ungroundedMessage,
      citations: [],
      grounded: false,
      warnings,
    };
  }

  return {
    answer: next,
    citations: valid,
    grounded: true,
    warnings,
  };
}
