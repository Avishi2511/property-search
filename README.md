<div align="center">

# 🏠 Basera

### Voice-first real-estate search that asks the *right* next question — not the next question on a form

[![Backend](https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white)](backend)
[![Frontend](https://img.shields.io/badge/frontend-React%2018%20%2B%20TypeScript-61DAFB?logo=react&logoColor=white)](frontend)
[![Tests](https://img.shields.io/badge/tests-126%20passing-brightgreen)](backend/tests)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](backend)
[![WebSocket](https://img.shields.io/badge/transport-WebSocket-black)](backend/app/api)

**[Demo flow](#-demo-flow) · [Why this is hard](#-why-this-is-a-hard-problem) · [Architecture](#-architecture) · [How discovery works](#-how-progressive-discovery-works) · [Running it](#-running-it)**

</div>

---

Real-estate search UIs make you fill out a form before they'll help you: city,
budget, bedrooms, locality, possession date — eight fields, in a fixed order,
before a single result appears. Half of them don't matter for your search;
the one that matters most is buried at the bottom.

**Basera throws out the form.** A buyer talks, in any order, with
corrections and hesitation and half-finished thoughts, the way people
actually describe what they want. After every utterance the backend
re-evaluates the *entire remaining candidate set* and asks — out loud —
whichever still-unknown question would cut that set down the most. It stops
asking as soon as a handful of strong matches remain, and it can explain
*why* it asked what it asked.

## 🎙 Demo flow

```text
Buyer   "I want a 3BHK in Bangalore around two crore."
Basera  → extracts city=Bangalore, bedrooms=3, budget≈₹1.8–2.2Cr
         → 231 of 550 properties still match
         → picks "locality" as the next question (~99% expected narrowing)

Buyer   "My wife's office is in Koramangala, but my parents will live with
         us, so being close to hospitals matters more than my commute."
Basera  → office_location=Koramangala        (context, not the buyer's locality)
         → parents_living_with_buyer=true
         → hospital_access=high, buyer_commute=low

Buyer   "Actually, I can stretch to 2.1 crore."
Basera  → budget revised: ₹2.0Cr (±10%) → ₹2.1Cr   [correction detected]

  … conversation continues until candidates ≤ 6, then:

Basera  "I've narrowed this down to 5 strong options. Let me walk you
         through the top matches …"   + ranked listings with match scores
```

## 🧩 Why this is a hard problem

| Naive approach | What breaks | What Basera does instead |
|---|---|---|
| Fixed questionnaire (budget → bedrooms → locality → …) | Asks questions that are already irrelevant given earlier answers; ignores what the buyer actually cares about | Re-scores **every** unanswered field after every turn and asks the one with the highest expected narrowing |
| LLM parses everything, including money/dates | Silent unit errors (`2 crore` → `2,00,000`), inconsistent on "under two crore", can't be unit-tested deterministically | Regex/rule-based extraction for money & dates, **structurally forbidden** from ever going through the LLM |
| Chatbot memory = raw transcript | Can't detect a correction ("actually, 2.1 crore") vs. a new fact; no confidence signal for ranking | Structured `BuyerProfile` with per-field confidence, correction history, and contradiction softening |

## 🏗 Architecture

```mermaid
flowchart LR
    subgraph Browser["Browser — React + TypeScript"]
        Speech["Web Speech API\n(STT / TTS, barge-in)"]
        UI["Conversation UI\nbuyer profile · search funnel\nnext-question explainer\nranked listings"]
        Speech <--> UI
    end

    UI <-->|"WebSocket\n/ws/conversation"| API

    subgraph Backend["FastAPI backend"]
        API["api/\nWebSocket endpoint"]
        Conv["conversation/\nturn loop"]
        Extract["extraction/\nmoney & date regex\n+ Gemini (open-ended only)"]
        Constraints["constraints/\nBuyerProfile\ncorrections · confidence"]
        Discovery["discovery/\nentropy scorer\nstop/select policy"]
        Search["search/\nhard-constraint filter\ngeo & commute tools"]
        Ranking["ranking/\nweighted soft-preference\nscoring"]
        Data[("properties/\n550 listings\n18 Bangalore localities")]

        API --> Conv
        Conv -->|"1. extract"| Extract
        Conv -->|"2. update state"| Constraints
        Conv -->|"3. filter"| Search
        Conv -->|"4. rank"| Ranking
        Conv -->|"5. ask or stop"| Discovery
        Search --> Data
        Discovery -.->|"reads candidate set"| Search
        Conv -->|"response"| API
    end

    style Discovery fill:#4c6ef5,color:#fff,stroke:#364fc7
    style Extract fill:#f8f9fa,color:#000,stroke:#adb5bd
```

## 🎯 How progressive discovery works

For every still-unanswered (or still-ambiguous) field, `discovery/scorer.py`
computes one number:

```
question_score = expected_filter_strength × buyer_relevance × uncertainty × priority
```

```mermaid
flowchart TD
    A["Candidate set after last turn\n(e.g. 231 properties)"] --> B{"For each unanswered field…"}
    B --> C["expected_filter_strength\nShannon entropy of the field's\nvalue distribution across candidates"]
    B --> D["buyer_relevance\nadjusted by context already known\n(e.g. parents moving in → hospitals matter)"]
    B --> E["uncertainty × priority\nhow unsure we are · how important the field is"]
    C --> F["question_score"]
    D --> F
    E --> F
    F --> G{"Highest-scoring\nquestion"}
    G -->|"ask it"| H["Buyer answers"]
    H --> A
    G -.->|"candidates ≤ 6\nOR max questions hit\nOR no question helps"| I["Stop → present ranked matches"]

    style F fill:#4c6ef5,color:#fff,stroke:#364fc7
    style I fill:#2f9e44,color:#fff,stroke:#2b8a3e
```

`expected_filter_strength` is 0 if every remaining property already agrees
on that field (asking would be useless) and high if an answer would split
the candidate set cleanly. `discovery/policy.py` picks the highest-scoring
question each turn and stops once candidates fall below a configurable
threshold (default 6), a max-questions cap is hit, or no remaining question
would help. This is a heuristic by design — `QuestionScorer` is a swappable
interface, not a fixed algorithm.

### Ranking

`ranking/scorer.py` scores each hard-filtered candidate on budget fit,
locality/commute proximity, possession timeline, amenities, parking, and
builder preference — weighted, and blended toward "neutral" by each
constraint's confidence, so a shaky guess influences ranking less than a
firm statement. Hard constraints are enforced as a filter *before* ranking
ever runs (`conversation/search_bridge.py` decides which constraints are
hard enough to filter vs. soft enough to only affect ordering).

## 🛠 Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite |
| Voice | Web Speech API (STT + TTS) behind a swappable `VoiceProvider` interface |
| Realtime transport | WebSocket (`/ws/conversation`) |
| Backend | FastAPI, Pydantic v2, Uvicorn |
| LLM (optional, gap-filling only) | Google Gemini — never used for money or dates |
| Testing | pytest, pytest-asyncio, httpx — 126 tests, Gemini mocked/disabled in CI |
| Dataset | 550 synthetic listings across 18 real Bangalore localities |

## 📁 Project structure

```text
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
    ws/             typed WebSocket client
    components/    ConversationPanel, BuyerProfilePanel, SearchSpaceFunnel,
                    NextQuestionExplainer, TopMatchesPanel
    format.ts       Cr/Lakh formatting, field labels, listing thumbnail gradients
    App.tsx         layout: sticky conversation sidebar + results main area
```

## 🚀 Running it

### Backend

```bash
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash; venv\Scripts\activate.bat on cmd.exe
pip install -r requirements.txt
cp .env.example .env           # optionally set GEMINI_API_KEY — see below
python -m app.properties.generate_dataset   # writes app/properties/data/*.json (already committed)
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


---

<div align="center">

Built by [Avishi Mittal](https://github.com/Avishi2511)

</div>
