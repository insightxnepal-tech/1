import { generateGroundedAnswer } from "@/lib/llm";
import { parseChatRequest } from "@/lib/http";
import type { ApiError, ChatResponse } from "@/lib/types";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(
  request: Request,
): Promise<NextResponse<ChatResponse | ApiError>> {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const parsed = parseChatRequest(payload);
  if ("error" in parsed) {
    return NextResponse.json({ error: parsed.error }, { status: 400 });
  }

  const result = await generateGroundedAnswer(parsed);
  return NextResponse.json(result);
}
