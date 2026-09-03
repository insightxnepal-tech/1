import { getCorpus, listActs } from "@/lib/corpus";
import type { CorpusResponse } from "@/lib/types";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET(): Promise<NextResponse<CorpusResponse>> {
  return NextResponse.json({
    acts: listActs(),
    sectionCount: getCorpus().length,
  });
}
