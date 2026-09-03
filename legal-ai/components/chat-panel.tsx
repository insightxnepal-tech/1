"use client";

import { Disclaimer } from "@/components/disclaimer";
import { SourceDrawer } from "@/components/source-drawer";
import type {
  ActSummary,
  ChatMessage,
  ChatResponse,
  Language,
  LanguagePreference,
  RetrievedSection,
} from "@/lib/types";
import { useMemo, useState } from "react";

type ChatPanelProps = {
  acts: ActSummary[];
};

type VisibleMessage = ChatMessage & {
  citations?: ChatResponse["citations"];
  grounded?: boolean;
};

const PROMPTS_EN = [
  "What is the minimum marriage age in Nepal?",
  "How many hours can an employer require in a week?",
  "Does the Constitution allow the death penalty?",
];

const PROMPTS_NE = [
  "नेपालमा विवाहको न्यूनतम उमेर कति हो?",
  "एक हप्तामा कति घण्टा काम लगाउन पाइन्छ?",
  "संविधानले मृत्युदण्ड अनुमति दिन्छ?",
];

export function ChatPanel({ acts }: ChatPanelProps) {
  const [language, setLanguage] = useState<LanguagePreference>("auto");
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<VisibleMessage[]>([]);
  const [sources, setSources] = useState<RetrievedSection[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);

  const prompts = language === "ne" ? PROMPTS_NE : PROMPTS_EN;
  const uiLanguage: Language = language === "ne" ? "ne" : "en";

  const actLine = useMemo(
    () =>
      acts
        .map((act) =>
          uiLanguage === "ne"
            ? `${act.actTitleNe} (${act.sectionCount})`
            : `${act.actTitleEn} (${act.sectionCount})`,
        )
        .join(" · "),
    [acts, uiLanguage],
  );

  async function send(question: string) {
    const trimmed = question.trim();
    if (!trimmed || pending) return;

    const nextMessages: VisibleMessage[] = [
      ...messages,
      { role: "user", content: trimmed },
    ];
    setMessages(nextMessages);
    setInput("");
    setPending(true);
    setError(null);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: nextMessages.map(({ role, content }) => ({ role, content })),
          language,
        }),
      });
      const payload = (await response.json()) as ChatResponse | { error: string };
      if (!response.ok || "error" in payload) {
        throw new Error("error" in payload ? payload.error : "Chat request failed.");
      }

      setSources(payload.sources);
      setWarnings(payload.warnings);
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: payload.answer,
          citations: payload.citations,
          grounded: payload.grounded,
        },
      ]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Chat request failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="grid flex-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="flex min-h-[70vh] flex-col rounded-2xl border border-white/10 bg-ink-900/80 shadow-folio">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
          <div>
            <p className="text-sm text-parchment-200">
              {uiLanguage === "ne" ? "भाषा" : "Answer language"}
            </p>
            <div className="mt-1 inline-flex rounded-full bg-ink-800 p-1 text-xs">
              {(
                [
                  ["auto", "Auto / स्वतः"],
                  ["en", "English"],
                  ["ne", "नेपाली"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setLanguage(value)}
                  className={`rounded-full px-3 py-1 ${
                    language === value
                      ? "bg-crimson-500 text-white"
                      : "text-parchment-200 hover:text-white"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <p className="max-w-xs text-right text-xs leading-5 text-parchment-200">
            {actLine}
          </p>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          {messages.length === 0 ? (
            <div className="space-y-3">
              <p className="text-sm text-parchment-200">
                {uiLanguage === "ne"
                  ? "कानुनी प्रश्न सोध्नुहोस्। उत्तरमा [ऐनको नाम, दफा नम्बर] अनिवार्य छ।"
                  : "Ask a statutory question. Every legal claim must carry [Act Title, Section (Dafa) Number]."}
              </p>
              <div className="flex flex-wrap gap-2">
                {prompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => void send(prompt)}
                    className="rounded-full border border-white/15 bg-ink-800 px-3 py-2 text-left text-sm text-parchment-50 hover:border-saffron-400/60"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {messages.map((message, index) => (
            <article
              key={`${message.role}-${index}`}
              className={`max-w-[42rem] rounded-2xl px-4 py-3 text-sm leading-6 ${
                message.role === "user"
                  ? "ml-auto bg-crimson-500/20 text-parchment-50"
                  : "bg-ink-800 text-parchment-50"
              }`}
            >
              <p className="whitespace-pre-wrap font-devanagari">{message.content}</p>
              {message.role === "assistant" ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {message.citations?.map((citation) => (
                    <span
                      key={citation.raw}
                      className="citation-chip rounded-full bg-saffron-500/15 px-2 py-1 text-xs text-saffron-400"
                    >
                      {citation.raw}
                    </span>
                  ))}
                  {message.grounded === false ? (
                    <span className="rounded-full bg-crimson-500/20 px-2 py-1 text-xs text-crimson-400">
                      ungrounded
                    </span>
                  ) : null}
                </div>
              ) : null}
            </article>
          ))}

          {pending ? (
            <p className="text-sm text-parchment-200">
              {uiLanguage === "ne" ? "संग्रह जाँच हुँदैछ…" : "Checking the statutory corpus…"}
            </p>
          ) : null}
          {error ? <p className="text-sm text-crimson-400">{error}</p> : null}
          {warnings.map((warning) => (
            <p key={warning} className="text-xs text-saffron-400">
              {warning}
            </p>
          ))}
        </div>

        <form
          className="border-t border-white/10 p-4"
          onSubmit={(event) => {
            event.preventDefault();
            void send(input);
          }}
        >
          <label className="sr-only" htmlFor="legal-question">
            Legal question
          </label>
          <div className="flex gap-2">
            <textarea
              id="legal-question"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              rows={2}
              placeholder={
                uiLanguage === "ne"
                  ? "उदाहरण: श्रम ऐनमा दैनिक कामको समय कति हो?"
                  : "Example: What does the Labour Act say about daily working hours?"
              }
              className="min-h-[68px] flex-1 resize-none rounded-xl border border-white/10 bg-ink-950 px-3 py-2 text-sm text-parchment-50 outline-none ring-saffron-400 placeholder:text-parchment-200/60 focus:ring-2"
            />
            <button
              type="submit"
              disabled={pending || !input.trim()}
              className="self-end rounded-xl bg-crimson-500 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
            >
              {uiLanguage === "ne" ? "पठाउनुहोस्" : "Ask"}
            </button>
          </div>
        </form>
      </div>

      <aside className="space-y-4">
        <Disclaimer />
        <div className="rounded-2xl border border-white/10 bg-ink-900/80 p-4">
          <h2 className="font-display text-lg text-parchment-50">
            {uiLanguage === "ne" ? "आधार अंशहरू" : "Grounded excerpts"}
          </h2>
          <div className="mt-3 max-h-[70vh] overflow-y-auto pr-1">
            <SourceDrawer sources={sources} />
          </div>
        </div>
      </aside>
    </section>
  );
}
