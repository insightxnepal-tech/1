import { formatCitation } from "./citations";
import type { Language, RetrievedSection } from "./types";

export const CITATION_RULE_EN =
  "ALWAYS format legal citations strictly as [Act Title, Section (Dafa) Number]. Example: [National Civil Code, 2074, Section (Dafa) 70].";

export const CITATION_RULE_NE =
  "नेपाली उत्तरमा उद्धरण यसरी लेख्नुहोस्: [ऐनको नाम, दफा नम्बर]। उदाहरण: [राष्ट्रिय देवानी संहिता, २०७४, दफा ७०]। अङ्ग्रेजी वाक्यमा अनिवार्य रूपमा [Act Title, Section (Dafa) Number] प्रयोग गर्नुहोस्।";

export function buildSystemPrompt(language: Language): string {
  const bilingualBlock =
    language === "ne"
      ? `तपाईं नेपाली कानुनी अनुसन्धान सहायक हुनुहुन्छ। उत्तर देवनागरीमा दिनुहोस्।\n${CITATION_RULE_NE}\n${CITATION_RULE_EN}`
      : `You are a Nepalese legal research assistant. Answer in English unless the user writes in Nepali.\n${CITATION_RULE_EN}\n${CITATION_RULE_NE}`;

  return [
    bilingualBlock,
    "Grounding rules:",
    "- Use ONLY the statutory excerpts provided in the user message.",
    "- Every legal proposition must be followed by a citation in the required format.",
    "- Never invent an Act title or a Section (Dafa) number.",
    "- If the excerpts do not contain the answer, say you cannot confirm it from the available corpus.",
    "- Do not present this as a substitute for licensed legal advice in Nepal.",
    "- Prefer the official English Act title in English citations, and the Nepali title in Devanagari citations.",
  ].join("\n");
}

export function formatRetrievedContext(sections: readonly RetrievedSection[]): string {
  if (sections.length === 0) {
    return "No statutory excerpts were retrieved.";
  }

  return sections
    .map((section, index) => {
      const enCite = formatCitation(section.actTitleEn, section.sectionNumber, "en");
      const neCite = formatCitation(section.actTitleNe, section.sectionNumber, "ne");
      return [
        `Excerpt ${index + 1} ${enCite} / ${neCite}`,
        `Heading EN: ${section.headingEn}`,
        `Heading NE: ${section.headingNe}`,
        `English: ${section.textEn}`,
        `नेपाली: ${section.textNe}`,
      ].join("\n");
    })
    .join("\n\n");
}

export function buildUserPrompt(
  question: string,
  sections: readonly RetrievedSection[],
  language: Language,
): string {
  const instruction =
    language === "ne"
      ? "तलका अंशबाट मात्र उत्तर दिनुहोस्। प्रत्येक कानुनी वाक्यपछि अनिवार्य उद्धरण राख्नुहोस्।"
      : "Answer only from the excerpts below. Place a required citation after every legal statement.";

  return [
    instruction,
    "",
    `Question: ${question}`,
    "",
    "Retrieved statutory excerpts:",
    formatRetrievedContext(sections),
  ].join("\n");
}

export function ungroundedMessage(language: Language): string {
  return language === "ne"
    ? "उपलब्ध कानुनी संग्रहमा यो प्रश्नको आधार भेटिएन। मैले दफा वा ऐन अनुमान गरेर उत्तर दिन मिल्दैन।"
    : "I cannot confirm this from the available statutory corpus and will not invent an Act title or Section (Dafa) number.";
}
