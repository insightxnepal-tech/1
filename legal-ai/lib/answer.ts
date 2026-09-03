import { bilingualCitationPair, enforceCitations, formatCitation } from "./citations";
import { ungroundedMessage } from "./prompts";
import type { Language, RetrievedSection } from "./types";

function pickLeadSections(sections: readonly RetrievedSection[], limit = 3): RetrievedSection[] {
  return sections.slice(0, limit);
}

export function buildExtractiveAnswer(
  question: string,
  sections: readonly RetrievedSection[],
  language: Language,
): { answer: string; usedSectionIds: string[] } {
  const lead = pickLeadSections(sections);
  if (lead.length === 0) {
    return { answer: ungroundedMessage(language), usedSectionIds: [] };
  }

  const paragraphs = lead.map((section) => {
    const cite = formatCitation(
      language === "ne" ? section.actTitleNe : section.actTitleEn,
      section.sectionNumber,
      language,
    );
    const pair = bilingualCitationPair(section);
    const body = language === "ne" ? section.textNe : section.textEn;
    const heading = language === "ne" ? section.headingNe : section.headingEn;
    const extra = language === "ne" ? pair.en : pair.ne;
    return language === "ne"
      ? `${heading} सम्बन्धमा संग्रह भन्छ: ${body} ${cite} ${extra}`
      : `On ${heading.toLowerCase()}, the corpus states: ${body} ${cite} ${extra}`;
  });

  const preface =
    language === "ne"
      ? `तपाईंको प्रश्न (“${question.trim()}”) का लागि उपलब्ध ऐनका अंश यस प्रकार छन्। यो अनुसन्धान सहायता हो, कानुनी राय होइन।`
      : `For your question (“${question.trim()}”), the available statutory excerpts say the following. This is research assistance, not legal advice.`;

  return {
    answer: [preface, ...paragraphs].join("\n\n"),
    usedSectionIds: lead.map((section) => section.id),
  };
}

export function finalizeAnswer(
  draft: string,
  sections: readonly RetrievedSection[],
  language: Language,
) {
  return enforceCitations(draft, sections, language, ungroundedMessage(language));
}
