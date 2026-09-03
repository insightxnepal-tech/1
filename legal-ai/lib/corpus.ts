import { LEGAL_CORPUS } from "./corpus-data";
import type { ActSummary, CorpusSection } from "./types";

export function getCorpus(): readonly CorpusSection[] {
  return LEGAL_CORPUS;
}

export function getSectionById(id: string): CorpusSection | undefined {
  return LEGAL_CORPUS.find((section) => section.id === id);
}

export function listActs(): ActSummary[] {
  const grouped = new Map<string, ActSummary>();

  for (const section of LEGAL_CORPUS) {
    const key = `${section.actTitleEn}::${section.actYearBs}`;
    const existing = grouped.get(key);
    if (existing) {
      existing.sectionCount += 1;
      continue;
    }
    grouped.set(key, {
      actTitleEn: section.actTitleEn,
      actTitleNe: section.actTitleNe,
      actYearBs: section.actYearBs,
      actYearAd: section.actYearAd,
      sectionCount: 1,
    });
  }

  return [...grouped.values()];
}

export function findSectionsForCitation(
  actTitle: string,
  sectionNumber: string,
): CorpusSection[] {
  const needle = sectionNumber.trim();
  return LEGAL_CORPUS.filter(
    (section) =>
      section.sectionNumber === needle &&
      (section.actTitleEn === actTitle || section.actTitleNe === actTitle),
  );
}
