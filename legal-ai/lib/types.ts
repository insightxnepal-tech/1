export type Language = "en" | "ne";

export type LanguagePreference = Language | "auto";

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

export type CorpusSection = {
  id: string;
  actTitleEn: string;
  actTitleNe: string;
  actYearBs: string;
  actYearAd: string;
  sectionNumber: string;
  headingEn: string;
  headingNe: string;
  textEn: string;
  textNe: string;
  tags: string[];
};

export type ActSummary = {
  actTitleEn: string;
  actTitleNe: string;
  actYearBs: string;
  actYearAd: string;
  sectionCount: number;
};

export type RetrievedSection = CorpusSection & {
  score: number;
};

export type Citation = {
  actTitle: string;
  sectionNumber: string;
  raw: string;
  language: Language;
  valid: boolean;
  matchedSectionId?: string;
};

export type ChatRequest = {
  messages: ChatMessage[];
  language?: LanguagePreference;
};

export type ChatResponse = {
  answer: string;
  citations: Citation[];
  sources: RetrievedSection[];
  language: Language;
  grounded: boolean;
  warnings: string[];
  usedModel: "extractive-corpus" | "openai";
};

export type SearchRequest = {
  query: string;
  language?: LanguagePreference;
  limit?: number;
};

export type SearchResponse = {
  query: string;
  language: Language;
  results: RetrievedSection[];
};

export type CorpusResponse = {
  acts: ActSummary[];
  sectionCount: number;
};

export type ApiError = {
  error: string;
};
