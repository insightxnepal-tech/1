import { ChatPanel } from "@/components/chat-panel";
import { listActs } from "@/lib/corpus";

export default function HomePage() {
  const acts = listActs();

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-6 sm:px-6 lg:px-8">
      <header className="mb-6 flex flex-col gap-4 border-b border-white/10 pb-6 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="font-devanagari text-sm tracking-[0.18em] text-saffron-400">
            न्याय / NYAYA
          </p>
          <h1 className="mt-2 font-display text-3xl leading-tight text-parchment-50 sm:text-4xl">
            Nepalese Legal Research Agent
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-parchment-200">
            Answers are grounded in a curated statutory corpus and must cite{" "}
            <code className="rounded bg-white/10 px-1.5 py-0.5 text-saffron-400">
              [Act Title, Section (Dafa) Number]
            </code>
            . English and देवनागरी are first-class. This is not legal advice.
          </p>
        </div>
        <p className="font-devanagari max-w-sm text-sm leading-6 text-parchment-200">
          प्रत्येक कानुनी वाक्यपछि दफा उद्धरण अनिवार्य छ। संग्रहमा नभएको ऐन अनुमान गरिँदैन।
        </p>
      </header>
      <ChatPanel acts={acts} />
    </main>
  );
}
