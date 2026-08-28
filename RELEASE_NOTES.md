Built in 2 hours at **Fast Hacks - Hack Night - with OpenAI Codex**, Tokyo, 2026-08.

**What it does:** Eliminates Tokyo transit hallucinations by pairing fuzzy vibe-based place discovery with deterministic subway route calculation.

## Stack

- **Qdrant** — Vector database for semantic similarity search over Tokyo points of interest.
- **Neo4j** — Graph database modeling Tokyo subway topology for deterministic route calculation.
- **OpenAI** — Intent extraction, embeddings, query orchestration, and natural language synthesis.
- **FastAPI + Jinja2** — Server-rendered post-hackathon frontend.
- **HTMX + Alpine.js** — Lightweight interaction without a heavy SPA framework.
- **Streamlit** — Original fallback interface for quick local testing.

## What's in v1.1.0

- Added a judge-facing FastAPI frontend in `web_app.py`.
- Added a custom Tokyo route cockpit UI with prompt, SVG transit map, best-answer panel, candidate ranking, and GraphRAG proof trail.
- Added HTMX-powered prompt submission and seed actions, with Alpine.js used for small UI state.
- Kept the existing Streamlit app intact as a fallback.
- Documented the post-hackathon frontend rationale in the README appendix.

## What's in v1.0.0

- Natural language prompt parsing for experience preferences and transit constraints.
- Hybrid GraphRAG pipeline combining vector similarity matching with graph shortest-path traversals.
- One-click sample demo buttons with execution log transparency.

**Known limits:** Seeded dataset covering key Tokyo stations and attractions only; uses in-memory Qdrant instance; no user authentication.

## Result

Demoed

## Docs

- `PRD.md` · `SUBMISSION_DESC.md` · `hackathon-fasthack.md`
