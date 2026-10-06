# FitProof implementation log

Existing COVATA is a separate application. FitProof is isolated here; existing source and configuration are preserved.

## Ordered checkpoints
1. Scaffold and run frontend/backend.
2. SerpApi adapter and actual response check.
3. Source normalization and document retrieval.
4. Typed AI extraction with swappable Gemini/Claude adapter.
5. Evidence validation.
6. Independent compatibility rules and focused tests.
7. Bounded LangGraph workflow.
8. FastAPI run, events, clarification, offer and report endpoints.
9. Input UI.
10. Backend-generated progress.
11. Results and evidence drawer.
12. SQLite persistence.
13. Query caching and recoverable failures.
14. Offline automated integration and browser tests.
15. UI polish and responsive review.
16. README, deployment setup and engineering documentation.

## External dependency
Live SerpApi and LLM credentials were absent at initial inspection. Phase 2's authenticated live checkpoint remains pending until configured; isolated contract tests and subsequent independently verifiable work can proceed. Replay is an explicit separate mode, never an automatic fallback. The final status must distinguish tests from live provider verification.

## Verification record
Completed offline verification:

- Backend: `uv run pytest -q` — 43 tests passed.
- Backend lint: `uv run ruff check app tests` — clean.
- Frontend: `npm run build` — TypeScript and Vite production build passed.
- Browser smoke: replay run, conflict candidate, evidence drawer/source links and 390px responsive layout passed.
- Persistence: saved evidence reopens from SQLite; interrupted runs recover without remaining falsely `investigating`.

Live provider verification remains pending until authenticated SerpApi and LLM keys are configured. No live-success claim is made here.
