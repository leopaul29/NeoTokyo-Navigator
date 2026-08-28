# NeoTokyo Navigator

Lightweight GraphRAG demo for the Fast Hacks Tokyo hackathon. The primary UI is a FastAPI + HTMX route cockpit that combines:

- OpenAI for multilingual intent extraction and embeddings.
- Qdrant for semantic place search.
- Neo4j for route reasoning over a tiny Tokyo transit graph.
- Local fallbacks for the same flow when cloud tools are not configured yet.

The original Streamlit UI is still available as a fallback, but the FastAPI frontend is the recommended demo surface.

## Quick Start

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

If `py` is not available, install Python 3.11+ from [python.org](https://www.python.org/downloads/) and enable "Add Python to PATH".

For the judge-facing frontend, run:

```powershell
uvicorn web_app:app --reload
```

Then open <http://127.0.0.1:8000>.

For the original Streamlit fallback, run:

```powershell
streamlit run app.py
```

The app works immediately in fallback mode. Add credentials to `.env`, restart the server, then use the `Seed` action to seed Qdrant and Neo4j.

## Current Database Scope

This is a deliberately small hackathon demo graph, not a full Tokyo or full Yamanote dataset.

Current stations:

- Shibuya
- Harajuku
- Yoyogi
- Shinjuku
- Shinjuku-gyoemmae
- Asakusa

Current places:

- Yoyogi Park
- Shinjuku Gyoen National Garden
- Meiji Shrine
- Senso-ji Temple
- Blue Bottle Coffee Shibuya

Current transit links:

- Shibuya <-> Harajuku, JR Yamanote Line
- Harajuku <-> Yoyogi, JR Yamanote Line
- Yoyogi <-> Shinjuku, JR Yamanote Line
- Shinjuku <-> Shinjuku-gyoemmae, Tokyo Metro Marunouchi Line
- Shibuya <-> Asakusa, Tokyo Metro Ginza Line

## Adding More Locations

Add new locations in [app.py](app.py), then seed the connected databases again from the web UI.

For each new place:

1. Add it to `PLACES` with a clear `description`, `kind`, `tags`, and nearest `station_id`.
2. If its nearest station is new, add that station to `STATIONS`.
3. If the station is new, connect it to the route graph with one or more `TRANSIT_EDGES`.
4. Restart the running server.
5. Click `Seed`.

You generally need both databases:

- Qdrant stores place descriptions as embeddings, so fuzzy searches like "quiet cafe", "traditional temple", or "large park" can find the right candidates.
- Neo4j stores stations, places, and transit links, so the app can calculate stops, transfers, and route feasibility without relying on the LLM's memory.

The seed process uses upserts/`MERGE`, so it refreshes the demo records without deleting unrelated data.

## Tool Setup

### OpenAI

1. Sign in at [platform.openai.com](https://platform.openai.com/).
2. Create an API key.
3. Put it in `.env` as `OPENAI_API_KEY=...`.
4. Keep `OPENAI_MODEL` and `OPENAI_EMBEDDING_MODEL` as-is unless your account uses different model names.

### Qdrant

Option A, local Docker:

```powershell
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

Use:

```env
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
```

Option B, Qdrant Cloud:

1. Sign in at [cloud.qdrant.io](https://cloud.qdrant.io/).
2. Create a free cluster.
3. Copy the cluster URL and API key.
4. Set `QDRANT_URL` and `QDRANT_API_KEY` in `.env`.

### Neo4j

Option A, local Docker:

```powershell
docker run --name neotokyo-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:2026.07.1
```

Use:

```env
NEO4J_URI=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j
```

Option B, Neo4j Aura:

1. Sign in at [console.neo4j.io](https://console.neo4j.io/).
2. Create an AuraDB instance.
3. Copy the connection URI, username, and password.
4. Set `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE` in `.env`.

## Demo Script

Try:

```text
I am at Shibuya, find me a large park with few transfers.
```

Expected result: Qdrant/local vector search surfaces Yoyogi Park and Shinjuku Gyoen. Neo4j/local graph routing ranks Yoyogi Park first because it is one direct stop from Shibuya.

Then try:

```text
Je suis a Shinjuku, je veux visiter un temple traditionnel avec maximum un changement.
```

Expected result: the app recommends Meiji Shrine with a simple JR Yamanote route.

## Appendix: Post-Hackathon Frontend

The hackathon version used Streamlit because it was the fastest way to prove the GraphRAG flow in two hours. After the demo, the frontend was rebuilt as a lightweight FastAPI interface so the product story is easier to understand in a short judging window.

The new UI is designed as a Tokyo route cockpit:

- The prompt sits at the top so the user intent is immediately visible.
- The center of the screen shows the transit graph and selected route, making the "verified path" part obvious without explanation.
- The result panel highlights the best destination, travel time, stops, transfers, and route steps.
- The proof strip shows the pipeline in four beats: intent extraction, Qdrant vibe search, Neo4j route validation, and grounded answer.

The frontend intentionally avoids a heavy single-page framework. FastAPI and Jinja2 render the page server-side, HTMX swaps navigation results without a full reload, Alpine.js handles small interactive states like logs, and CSS/SVG provide the custom visual identity. The Streamlit app remains available in [app.py](app.py) as a fallback.

## References

- [Streamlit installation](https://docs.streamlit.io/get-started/installation)
- [OpenAI API key help](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key)
- [Qdrant local quickstart](https://qdrant.tech/documentation/quick-start/)
- [Neo4j Docker guide](https://neo4j.com/docs/operations-manual/current/docker/introduction/)
