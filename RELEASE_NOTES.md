Built in 2 hours at **Fast Hacks - Hack Night - with OpenAI Codex**, Tokyo, 2026-08.

**What it does:** Eliminates Tokyo transit hallucinations by pairing fuzzy vibe-based place discovery with deterministic subway route calculation.

## Stack

- **Qdrant** — Vector database for semantic similarity search over Tokyo points of interest.
- **Neo4j** — Graph database modeling Tokyo subway topology for deterministic route calculation.
- **OpenAI (GPT-4o)** — Intent extraction, query orchestration, and natural language synthesis.
- **Streamlit** — Web interface for instant demo queries and real-time execution log visualization.

## What's in v1.0.0

- Natural language prompt parsing for experience preferences and transit constraints.
- Hybrid GraphRAG pipeline combining vector similarity matching with graph shortest-path traversals.
- One-click sample demo buttons with execution log transparency.

**Known limits:** Seeded dataset covering key Tokyo stations and attractions only; uses in-memory Qdrant instance; no user authentication.

## Result

Demoed

## Docs

- `PRD.md` · `SUBMISSION_DESC.md` · `hackathon-fasthack.md`
