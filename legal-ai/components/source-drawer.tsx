import { formatCitation } from "@/lib/citations";
import type { RetrievedSection } from "@/lib/types";

type SourceDrawerProps = {
  sources: RetrievedSection[];
};

export function SourceDrawer({ sources }: SourceDrawerProps) {
  if (sources.length === 0) {
    return (
      <p className="text-sm text-parchment-200">
        No grounded excerpts yet. Ask a question about a Nepalese statute.
      </p>
    );
  }

  return (
    <ol className="space-y-3">
      {sources.map((source) => (
        <li
          key={source.id}
          className="rounded-xl border border-white/10 bg-ink-800/80 p-3"
        >
          <p className="citation-chip text-xs text-saffron-400">
            {formatCitation(source.actTitleEn, source.sectionNumber, "en")}
          </p>
          <p className="font-devanagari mt-1 text-xs text-parchment-200">
            {formatCitation(source.actTitleNe, source.sectionNumber, "ne")}
          </p>
          <h3 className="mt-2 text-sm font-medium text-parchment-50">
            {source.headingEn}
          </h3>
          <p className="font-devanagari text-sm text-parchment-200">
            {source.headingNe}
          </p>
          <p className="mt-2 text-sm leading-6 text-parchment-100">{source.textEn}</p>
          <p className="font-devanagari mt-2 text-sm leading-7 text-parchment-200">
            {source.textNe}
          </p>
        </li>
      ))}
    </ol>
  );
}
