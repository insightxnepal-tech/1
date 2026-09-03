import { parseSearchQuery } from "@/lib/http";
import { resolveLanguage } from "@/lib/language";
import { retrieveSections } from "@/lib/rag";
import type { ApiError, SearchResponse } from "@/lib/types";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET(
  request: Request,
): Promise<NextResponse<SearchResponse | ApiError>> {
  const parsed = parseSearchQuery(new URL(request.url));
  if ("error" in parsed) {
    return NextResponse.json({ error: parsed.error }, { status: 400 });
  }

  const language = resolveLanguage(parsed.language, parsed.query);
  const results = retrieveSections(parsed.query, parsed.limit, language);

  return NextResponse.json({
    query: parsed.query,
    language,
    results,
  });
}
