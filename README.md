# Voice Search With Progressive Constraint Discovery

A voice-first real-estate search agent that progressively discovers a buyer's
actual requirements through natural conversation. Instead of a fixed
questionnaire, the agent picks whichever unknown piece of information would
most reduce the property search space next.

## Status

Under active step-by-step build. Current state: repo scaffold only
(backend + frontend boot, no product logic yet).

## Structure

```
backend/    FastAPI app: constraint engine, extraction, discovery, search, ranking
frontend/   React + Vite UI: conversation panel, live buyer profile, search-space funnel
```

## Backend

```bash
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash; use venv\Scripts\activate.bat on cmd
pip install -r requirements.txt
cp .env.example .env           # optionally set GEMINI_API_KEY
uvicorn app.main:app --reload
pytest
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Design notes

- `GEMINI_API_KEY` is optional. Numeric values (budget, dates) are always
  parsed deterministically, never trusted from the LLM alone. Without a key,
  the system falls back to rule-based extraction only.
- Voice uses the browser's native Web Speech API in the MVP, behind a
  `VoiceProvider` interface so it can later be swapped for a dedicated
  realtime voice API without touching the backend.
- The core discovery engine is fully testable via text, with no dependency
  on voice.
