import type { Language, LanguagePreference } from "./types";

const DEVANAGARI_RE = /[\u0900-\u097F]/;

export function hasDevanagari(text: string): boolean {
  return DEVANAGARI_RE.test(text);
}

export function detectLanguage(text: string): Language {
  return hasDevanagari(text) ? "ne" : "en";
}

export function resolveLanguage(
  preference: LanguagePreference | undefined,
  text: string,
): Language {
  if (preference === "en" || preference === "ne") {
    return preference;
  }
  return detectLanguage(text);
}

const ASCII_DIGITS = "0123456789";
const DEVANAGARI_DIGITS = "०१२३४५६७८९";

export function toDevanagariDigits(value: string): string {
  return value.replace(/[0-9]/g, (digit) => {
    const index = ASCII_DIGITS.indexOf(digit);
    return index >= 0 ? DEVANAGARI_DIGITS[index] : digit;
  });
}

export function toAsciiDigits(value: string): string {
  return value.replace(/[०-९]/g, (digit) => {
    const index = DEVANAGARI_DIGITS.indexOf(digit);
    return index >= 0 ? ASCII_DIGITS[index] : digit;
  });
}

export function normalizeSectionNumber(value: string): string {
  return toAsciiDigits(value).replace(/\s+/g, "").replace(/^0+/, "") || "0";
}
