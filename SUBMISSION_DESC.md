**Project Name:** NeoTokyo Navigator

**Tagline:** Hallucination-free Tokyo vibe discovery and transit routing using Hybrid GraphRAG.

---

### Overview

Navigating Tokyo requires balancing fuzzy desires (_"a quiet traditional temple with a coffee shop nearby"_) with strict physical constraints (_subway lines, transfers, transit times_). Standard LLMs frequently hallucinate transit connections. **NeoTokyo Navigator** solves this by pairing semantic vector search for place discovery with a deterministic graph database for transit logic.

---

### What It Does

1. **Understands Natural Intent:** Users ask for experiences in plain English or Japanese (_"Find me a quiet park near Shibuya with no more than 1 subway transfer"_).
2. **Semantic Matching (Qdrant):** Performs vector similarity search over Tokyo points of interest to match the user's desired "vibe."
3. **Deterministic Routing (Neo4j):** Runs Cypher graph traversals (`shortestPath`) over real Tokyo subway network topologies to guarantee accurate, hallucination-free route options.
4. **Natural Synthesis (OpenAI):** Combines the matched destination and verified transit path into a clear, actionable travel plan.

---

### Tech Stack & Sponsor Integration

- **Qdrant:** High-performance vector database for semantic search on place descriptions.
- **Neo4j:** Graph database modeling Tokyo stations, lines, and physical connections.
- **OpenAI (GPT-4o / Codex):** Intent extraction, Cypher query orchestration, and natural language delivery.
- **Streamlit:** Lightweight interactive frontend.

---

### The Innovation: Hybrid GraphRAG

Instead of relying on LLM memory for spatial reasoning, **NeoTokyo Navigator** uses **Qdrant for the _WHAT_** (context & sentiment) and **Neo4j for the _HOW_** (guaranteed topological reality).
