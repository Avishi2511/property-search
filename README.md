# Basera — Voice Search With Progressive Constraint Discovery

A voice-first real-estate search agent for Bangalore that progressively
discovers a buyer's actual requirements through natural conversation.
Instead of a fixed questionnaire (budget? bedrooms? location? ...), the
agent decides — after every utterance — which still-unknown piece of
information would most reduce the property search space, and asks that
next. It stops asking once it has a small number of strong matches, and
explains why it picked each question.

This is **not** `voice → speech-to-text → chatbot → text-to-speech`. Voice
is a first-class interface into a discovery engine that maintains a
structured, confidence-scored buyer profile, handles corrections and
hesitation, and is fully testable through text alone.

## Status

Core engine, real-time voice, and web UI are built and working end-to-end.
126 backend tests passing. See [Architecture](#architecture) for what each
piece does and [Known limitations](#known-limitations) for what's
deliberately left as future work.

## Demo flow

```
Buyer: "I want a 3BHK in Bangalore around two crore."
  → extracts city=Bangalore, bedrooms=3, budget≈₹1.8–2.2Cr
  → 231 of 550 properties still match
  → picks "locality" as the next question (~99% expected narrowing)

Buyer: "My wife's office is in Koramangala, but my parents will live with
        us, so being close to hospitals matters more than my commute."
  → office_location=Koramangala (context, NOT the buyer's own locality)
  → parents_living_with_buyer=true, hospital_access=high, buyer_commute=low

Buyer: "Actually, I can stretch to 2.1 crore."
  → budget updated: previous=₹2.0Cr(±10%), current=₹2.1Cr, changed=true

... conversation continues until candidates ≤ 6, then:
  → "I've narrowed this down to N strong options. Let me walk you through
     the top matches: ..." + ranked listings with a match score.
```

## Architecture

```
Browser (React)
 ├─ Web Speech API (STT + TTS), behind a swappable VoiceProvider interface
 ├─ Conversation UI + live buyer profile, search-space funnel, next-question
 │  explainer, and a ranked listings grid
 └─ WebSocket ──────────────────────────────────────────────────┐
                                                                  │
FastAPI backend (/ws/conversation)                               │
 ├─ conversation/  turn loop: extract → update state → search → │
 │                 rank → decide (ask or stop) → respond ────────┘
 ├─ extraction/    deterministic money/date parsing + rule-based NLU,
 │                 with Gemini filling gaps for open-ended phrasing only
 ├─ constraints/   BuyerProfile state: corrections, confidence, history
 ├─ discovery/     question bank + heuristic scorer + stopping policy
 ├─ search/        hard-constraint filtering + geo/commute tools
 ├─ ranking/       deterministic weighted soft-preference scoring
 └─ properties/    synthetic Bangalore dataset (550 listings, 18 localities)
```

The engine (`conversation → extraction → constraints → discovery → search →
ranking`) is pure Python with no dependency on voice — every behavior above
is covered by a text-only test. Voice is one interface into it, not the
architecture.

### Why extraction never trusts the LLM for numbers or dates

`extraction/normalize.py` deterministically parses Indian money phrasing
(`2 crore`, `₹1.8 Cr`, `under 2 crore`, `one point eight crore`, hesitation
like `"maybe... 1.8... no, let's say 2"`) and conversational dates
(`"within six months"`, `"before Diwali next year"`, `"early 2028"`) with
regex, not an LLM call. `extraction/gemini_client.py` is used only for
open-ended fields (purpose, priorities, corrections, locality phrasing) and
is explicitly forbidden — in the prompt *and* in code, as a hard filter in
`extractor.py` — from ever supplying `budget` or `possession_date`.

### Progressive question selection

For each still-unanswered (or still-ambiguous) field, `discovery/scorer.py`
computes:

```
question_score = expected_filter_strength × buyer_relevance × uncertainty × priority
```

`expected_filter_strength` is the normalized Shannon entropy of that field's
distribution across the *current* candidate set — 0 if every remaining
property already agrees (useless to ask), high if an answer would split the
set well. `buyer_relevance` adjusts for context already established (e.g.
hospital access matters more once parents are confirmed to be moving in).
`discovery/policy.py` picks the highest-scoring question and stops once
candidates fall below a configurable threshold (default 6), a max-questions
cap is hit, or no remaining question would help. This is a heuristic by
design (see the project brief) — `QuestionScorer` is a swappable interface,
not a fixed algorithm.

### Ranking

`ranking/scorer.py` scores each hard-filtered candidate on budget fit,
locality/commute proximity, possession timeline, amenities, parking, and
builder preference — weighted, and blended toward "neutral" by each
constraint's confidence, so a shaky guess influences ranking less than a
firm statement. Hard constraints are enforced as a filter before ranking
ever runs (`conversation/search_bridge.py` decides which constraints are
hard enough to filter vs. soft enough to only affect ordering).

## Project structure

```
backend/
  app/
    properties/    synthetic dataset generator + repository + Bangalore localities
    search/        SearchCriteria, hard filters, geo/commute/nearby-places tools
    ranking/       deterministic soft-preference scoring
    constraints/   BuyerProfile schema + update/correction/confirmation logic
    extraction/    money/date normalization, rule-based NLU, Gemini fallback
    discovery/     question bank, entropy-based scorer, stop/select policy
    conversation/  per-turn pipeline, response templates, hard-constraint bridge
    api/           /ws/conversation WebSocket endpoint
    main.py        FastAPI app
  tests/           126 tests across every module above
frontend/
  src/
    voice/         VoiceProvider interface + WebSpeechProvider (STT/TTS, barge-in)
    ws/            typed WebSocket client
    components/    ConversationPanel, BuyerProfilePanel, SearchSpaceFunnel,
                   NextQuestionExplainer, TopMatchesPanel
    format.ts      Cr/Lakh formatting, field labels, listing thumbnail gradients
    App.tsx        layout: sticky conversation sidebar + results main area
```

## Running it

### Backend

```bash
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash; venv\Scripts\activate.bat on cmd.exe
pip install -r requirements.txt
cp .env.example .env           # optionally set GEMINI_API_KEY — see below
python -m app.properties.generate_dataset   # writes app/properties/data/*.json (already committed, re-run only if you change the generator)
uvicorn app.main:app --reload
pytest                         # 126 tests
```

### Frontend

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173, expects the backend on ws://localhost:8000
```

Open the frontend URL in **Chrome** (Web Speech API support) and either
type or click the mic and talk.

### Environment variables (`backend/.env`)

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | No | Enables LLM-assisted extraction for open-ended phrasing (purpose, priorities, unusual locality references). Without it, the system runs on rule-based extraction alone — weaker on open-ended phrasing, but fully functional and deterministic. Never used for money/dates regardless. |
| `HOST`, `PORT` | No | Uvicorn bind address, default `0.0.0.0:8000`. |

## Testing strategy

126 tests in `backend/tests/`, organized by layer: dataset/search filtering,
constraint state (corrections, confirmations, contradiction-softening),
deterministic money/date normalization, rule-based + LLM-merge extraction,
discovery scoring/stopping policy, ranking determinism, the search-criteria
bridge, the WebSocket API, and full end-to-end conversations against the
real 550-property dataset (including the spec's adversarial cases:
corrections, out-of-order info, hesitation, contradictions). Gemini is
mocked or disabled in every test — nothing in CI depends on a live API key.

Run everything: `cd backend && pytest -q`.

## Known limitations

- **Voice feedback loop**: without headphones, the mic can pick up the
  agent's own speaker output. Chrome's default capture applies some echo
  cancellation, which usually prevents false interrupts, but it isn't
  guaranteed. A production system would route through a dedicated
  acoustic-echo-cancelling pipeline — exactly why voice sits behind a
  swappable `VoiceProvider` interface.
- **Commute estimates** are straight-line distance ÷ an assumed 22 km/h
  average city speed, not a real routing engine.
- **Browser support**: voice requires Chrome (`webkitSpeechRecognition`).
  Other browsers fall back to typing — the UI detects and message this.
- **Gemini model pinning**: `_MODEL_NAME` in `extraction/gemini_client.py`
  is a fixed model string; if Google deprecates it, extraction logs a
  warning and falls back to rule-based only rather than failing the
  request — but the constant will need updating to restore LLM-assisted
  extraction.
- **`create-vite` pinned to v5** in the frontend setup instructions — the
  latest `create-vite` requires Node ≥20; this repo was scaffolded against
  Node 18. Not an issue once `npm install` has already run (only affects
  re-scaffolding from scratch).
- Builder names in the dataset are fictional, to avoid implying any real
  builder's association with this demo.
