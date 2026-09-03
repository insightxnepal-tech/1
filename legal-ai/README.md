# Nyaya — Nepalese Legal AI

Grounded statutory research assistant for Nepalese law. Chat answers are
retrieved from a bilingual corpus and **must** cite
`[Act Title, Section (Dafa) Number]`. Invented दफा numbers are stripped.

This is research assistance, not a substitute for licensed legal advice.

## Architecture

- Next.js 14 App Router (`app/api/.../route.ts`)
- Server Component shell in `app/page.tsx`; chat UI is a Client Component
- Typed API routes: `/api/chat`, `/api/search`, `/api/corpus`
- RAG + citation enforcement in `lib/` (`prompts.ts`, `rag.ts`, `citations.ts`)
- English and Devanagari are first-class

## Setup

```bash
cd legal-ai
cp .env.example .env.local   # OPENAI_API_KEY is optional
npm install
npm test
npm run dev
```

Without an API key, answers are synthesised from the local corpus only. Tests
never hit the network.

## Citation rule

English: `[National Civil Code, 2074, Section (Dafa) 70]`

नेपाली: `[राष्ट्रिय देवानी संहिता, २०७४, दफा ७०]`
