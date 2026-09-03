import { buildExtractiveAnswer, finalizeAnswer } from "./answer";
import { resolveLanguage } from "./language";
import { buildSystemPrompt, buildUserPrompt } from "./prompts";
import { retrieveGroundedSections } from "./rag";
import type {
  ChatMessage,
  ChatResponse,
  LanguagePreference,
} from "./types";

export type GenerateAnswerInput = {
  messages: ChatMessage[];
  language?: LanguagePreference;
};

function latestUserQuestion(messages: readonly ChatMessage[]): string {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role === "user" && message.content.trim()) {
      return message.content.trim();
    }
  }
  return "";
}

type OpenAiChatResponse = {
  choices?: Array<{
    message?: {
      content?: string;
    };
  }>;
};

async function completeWithOpenAi(
  systemPrompt: string,
  userPrompt: string,
): Promise<string> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY is not set");
  }

  const baseUrl = (process.env.OPENAI_BASE_URL ?? "https://api.openai.com/v1").replace(
    /\/$/,
    "",
  );
  const model = process.env.OPENAI_MODEL ?? "gpt-4o-mini";

  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      temperature: 0.1,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt },
      ],
    }),
  });

  if (!response.ok) {
    throw new Error(`OpenAI request failed with status ${response.status}`);
  }

  const payload = (await response.json()) as OpenAiChatResponse;
  const content = payload.choices?.[0]?.message?.content?.trim();
  if (!content) {
    throw new Error("OpenAI returned an empty completion");
  }
  return content;
}

export async function generateGroundedAnswer(
  input: GenerateAnswerInput,
): Promise<ChatResponse> {
  const question = latestUserQuestion(input.messages);
  const language = resolveLanguage(input.language, question);
  const sources = retrieveGroundedSections(question, 5, language);

  if (!question) {
    const empty = finalizeAnswer("", sources, language);
    return {
      answer: empty.answer,
      citations: empty.citations,
      sources,
      language,
      grounded: false,
      warnings: empty.warnings,
      usedModel: "extractive-corpus",
    };
  }

  let draft: string;
  let usedModel: ChatResponse["usedModel"] = "extractive-corpus";

  if (process.env.OPENAI_API_KEY) {
    try {
      draft = await completeWithOpenAi(
        buildSystemPrompt(language),
        buildUserPrompt(question, sources, language),
      );
      usedModel = "openai";
    } catch {
      const extracted = buildExtractiveAnswer(question, sources, language);
      draft = extracted.answer;
      usedModel = "extractive-corpus";
    }
  } else {
    draft = buildExtractiveAnswer(question, sources, language).answer;
  }

  const enforced = finalizeAnswer(draft, sources, language);
  return {
    answer: enforced.answer,
    citations: enforced.citations,
    sources,
    language,
    grounded: enforced.grounded,
    warnings: enforced.warnings,
    usedModel,
  };
}
