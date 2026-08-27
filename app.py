from __future__ import annotations

import hashlib
import heapq
import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import streamlit as st

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional until dependencies are installed
    load_dotenv = None

try:
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover
    GraphDatabase = None

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, PointStruct, VectorParams
except ImportError:  # pragma: no cover
    QdrantClient = None
    Distance = None
    PointStruct = None
    VectorParams = None


if load_dotenv:
    load_dotenv()


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "neotokyo_places")


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    kind: str
    station_id: str
    description: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class TransitEdge:
    a: str
    b: str
    line: str
    minutes: int
    stops: int


@dataclass
class Intent:
    start_station_id: str
    place_query: str
    max_transfers: int
    language: str
    source: str


@dataclass
class Candidate:
    place: Place
    score: float
    source: str


@dataclass
class Route:
    station_ids: list[str]
    station_names: list[str]
    lines: list[str]
    minutes: int
    stops: int
    transfers: int
    source: str


STATIONS: dict[str, Station] = {
    "shibuya": Station("shibuya", "Shibuya", ("shibuya", "渋谷", "渋谷駅")),
    "harajuku": Station("harajuku", "Harajuku", ("harajuku", "原宿", "原宿駅")),
    "yoyogi": Station("yoyogi", "Yoyogi", ("yoyogi", "代々木", "代々木駅")),
    "shinjuku": Station("shinjuku", "Shinjuku", ("shinjuku", "新宿", "新宿駅")),
    "shinjuku_gyoemmae": Station(
        "shinjuku_gyoemmae",
        "Shinjuku-gyoemmae",
        ("shinjuku gyoemmae", "shinjuku-gyoemmae", "新宿御苑前", "新宿御苑前駅"),
    ),
    "asakusa": Station("asakusa", "Asakusa", ("asakusa", "浅草", "浅草駅")),
}


PLACES: list[Place] = [
    Place(
        "yoyogi_park",
        "Yoyogi Park",
        "park",
        "harajuku",
        "A large relaxed urban park near Harajuku, ideal for greenery, walking, "
        "picnics, people-watching, and a low-transfer escape from Shibuya.",
        ("park", "large park", "grand parc", "公園", "green", "quiet", "nature"),
    ),
    Place(
        "shinjuku_gyoen",
        "Shinjuku Gyoen National Garden",
        "garden",
        "shinjuku_gyoemmae",
        "A spacious historic garden with traditional landscapes, lawns, seasonal "
        "flowers, and a calmer mood than central Shinjuku.",
        ("park", "garden", "grand parc", "jardin", "庭園", "quiet", "nature"),
    ),
    Place(
        "meiji_shrine",
        "Meiji Shrine",
        "shrine",
        "harajuku",
        "A traditional Shinto shrine set in a forest beside Harajuku, suited for "
        "history, quiet rituals, architecture, and classic Tokyo atmosphere.",
        ("temple", "shrine", "traditional", "sanctuaire", "神社", "伝統", "calm"),
    ),
    Place(
        "sensoji_temple",
        "Senso-ji Temple",
        "temple",
        "asakusa",
        "Tokyo's oldest Buddhist temple in Asakusa, famous for its gate, shopping "
        "street, incense, crowds, and very traditional sightseeing energy.",
        ("temple", "traditional", "historic", "寺", "浅草", "culture", "classic"),
    ),
    Place(
        "blue_bottle_shibuya",
        "Blue Bottle Coffee Shibuya",
        "cafe",
        "shibuya",
        "A modern specialty coffee stop in Shibuya for a calmer cafe break, light "
        "work, espresso, and a simple no-train detour.",
        ("cafe", "coffee", "quiet", "calme", "カフェ", "コーヒー", "work"),
    ),
]


TRANSIT_EDGES: list[TransitEdge] = [
    TransitEdge("shibuya", "harajuku", "JR Yamanote Line", 3, 1),
    TransitEdge("harajuku", "yoyogi", "JR Yamanote Line", 2, 1),
    TransitEdge("yoyogi", "shinjuku", "JR Yamanote Line", 4, 1),
    TransitEdge("shinjuku", "shinjuku_gyoemmae", "Tokyo Metro Marunouchi Line", 3, 1),
    TransitEdge("shibuya", "asakusa", "Tokyo Metro Ginza Line", 32, 18),
]


def normalize_latin(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def tokenize(text: str) -> set[str]:
    normalized = normalize_latin(expand_japanese_hints(text))
    return set(re.findall(r"[a-z0-9]+", normalized))


def expand_japanese_hints(text: str) -> str:
    expansions = []
    hints = {
        "公園": "park nature green",
        "庭園": "garden park nature",
        "寺": "temple traditional historic",
        "神社": "shrine temple traditional calm",
        "伝統": "traditional historic classic",
        "カフェ": "cafe coffee quiet",
        "コーヒー": "coffee cafe",
        "静か": "quiet calm",
        "乗り換え": "transfer change",
    }
    for key, value in hints.items():
        if key in text:
            expansions.append(value)
    return f"{text} {' '.join(expansions)}"


def place_by_id(place_id: str) -> Place | None:
    return next((place for place in PLACES if place.id == place_id), None)


def station_name(station_id: str) -> str:
    return STATIONS[station_id].name


def station_from_text(text: str) -> str | None:
    latin_text = normalize_latin(text)
    raw_text = text.lower()
    for station in STATIONS.values():
        for alias in station.aliases:
            if normalize_latin(alias) and normalize_latin(alias) in latin_text:
                return station.id
            if alias.lower() in raw_text:
                return station.id
    return None


def parse_max_transfers(text: str) -> int:
    normalized = normalize_latin(expand_japanese_hints(text))
    if re.search(r"(no|zero|0)\s+(transfer|change|correspondance)", normalized):
        return 0
    if re.search(r"(one|1|un|une)\s+(transfer|change|correspondance)", normalized):
        return 1
    if re.search(r"(few|peu|minimum|low|moins|less).*(transfer|change|correspondance)", normalized):
        return 1
    if "乗り換え" in text and ("少" in text or "以内" in text):
        return 1
    return 2


def clean_place_query(text: str, start_station_id: str | None) -> str:
    cleaned = text
    if start_station_id:
        for alias in STATIONS[start_station_id].aliases:
            cleaned = re.sub(re.escape(alias), " ", cleaned, flags=re.IGNORECASE)
    filler_patterns = [
        r"\bi am\b",
        r"\bi'm\b",
        r"\bfrom\b",
        r"\bat\b",
        r"\bje suis\b",
        r"\bdepuis\b",
        r"\ba\b",
        r"\bà\b",
        r"\btrouve[- ]?moi\b",
        r"\bfind me\b",
        r"\bwith\b",
        r"\bsans\b",
        r"\bcorrespondances?\b",
        r"\btransfers?\b",
        r"\bchanges?\b",
    ]
    for pattern in filler_patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?")
    return cleaned or text


def fallback_intent(user_text: str) -> Intent:
    start_station_id = station_from_text(user_text) or "shibuya"
    return Intent(
        start_station_id=start_station_id,
        place_query=clean_place_query(user_text, start_station_id),
        max_transfers=parse_max_transfers(user_text),
        language="auto",
        source="local parser",
    )


def openai_client() -> OpenAI | None:
    if not has_openai_config():
        return None
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def has_openai_config() -> bool:
    return bool(OpenAI and os.getenv("OPENAI_API_KEY"))


def extract_intent(user_text: str) -> tuple[Intent, list[str]]:
    trace = []
    client = openai_client()
    if not client:
        intent = fallback_intent(user_text)
        trace.append("OpenAI is not configured; used the local multilingual parser.")
        return intent, trace

    station_options = ", ".join(station.name for station in STATIONS.values())
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract route-search intent for a Tokyo travel assistant. "
                        "Return JSON with start_station, place_query, max_transfers, "
                        "and language. start_station must be one of: "
                        f"{station_options}. If unclear, use Shibuya. "
                        "place_query should be concise English search text."
                    ),
                },
                {"role": "user", "content": user_text},
            ],
        )
        data = json.loads(response.choices[0].message.content or "{}")
        station_id = station_from_text(str(data.get("start_station", ""))) or station_from_text(user_text) or "shibuya"
        intent = Intent(
            start_station_id=station_id,
            place_query=str(data.get("place_query") or clean_place_query(user_text, station_id)),
            max_transfers=int(data.get("max_transfers") if data.get("max_transfers") is not None else parse_max_transfers(user_text)),
            language=str(data.get("language") or "auto"),
            source=f"OpenAI {OPENAI_MODEL}",
        )
        trace.append(f"OpenAI extracted: from {station_name(intent.start_station_id)}, looking for '{intent.place_query}'.")
        return intent, trace
    except Exception as exc:  # pragma: no cover - depends on external service
        intent = fallback_intent(user_text)
        trace.append(f"OpenAI call failed ({exc}); used the local parser.")
        return intent, trace


def local_embedding(text: str, dimensions: int = 96) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def embed_text(text: str) -> list[float]:
    client = openai_client()
    if not client:
        return local_embedding(text)
    response = client.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def place_document(place: Place) -> str:
    return f"{place.name}. {place.kind}. {place.description}. Tags: {', '.join(place.tags)}."


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(left * right for left, right in zip(a, b))


def semantic_hints(text: str) -> set[str]:
    tokens = tokenize(text)
    hints = set()
    if tokens & {"park", "garden", "jardin", "parc", "nature", "green"}:
        hints.add("park")
    if tokens & {"temple", "shrine", "traditional", "historic", "sanctuaire"}:
        hints.add("temple")
    if tokens & {"cafe", "coffee", "calme", "quiet", "work"}:
        hints.add("cafe")
    return hints


def category_adjustment(place: Place, hints: set[str]) -> float:
    adjustment = 0.0
    if "park" in hints:
        adjustment += 0.75 if place.kind in {"park", "garden"} else -0.25
    if "temple" in hints:
        adjustment += 0.75 if place.kind in {"temple", "shrine"} else -0.25
    if "cafe" in hints:
        adjustment += 0.75 if place.kind == "cafe" else -0.25
    return adjustment


def local_place_search(query: str, limit: int = 3) -> list[Candidate]:
    query_vector = local_embedding(query)
    query_tokens = tokenize(query)
    hints = semantic_hints(query)
    candidates = []
    for place in PLACES:
        document = place_document(place)
        document_tokens = tokenize(document)
        overlap = len(query_tokens & document_tokens)
        vector_score = cosine_similarity(query_vector, local_embedding(document))
        score = vector_score + overlap * 0.18 + category_adjustment(place, hints)
        candidates.append(Candidate(place=place, score=score, source="local vector fallback"))
    return sorted(candidates, key=lambda item: item.score, reverse=True)[:limit]


def qdrant_client() -> QdrantClient | None:
    if not QdrantClient:
        return None
    url = os.getenv("QDRANT_URL")
    host = os.getenv("QDRANT_HOST")
    api_key = os.getenv("QDRANT_API_KEY") or None
    if url:
        return QdrantClient(url=url, api_key=api_key, timeout=6)
    if host:
        port = int(os.getenv("QDRANT_PORT", "6333"))
        return QdrantClient(host=host, port=port, api_key=api_key, timeout=6)
    return None


def has_qdrant_config() -> bool:
    return bool(QdrantClient and (os.getenv("QDRANT_URL") or os.getenv("QDRANT_HOST")))


def seed_qdrant() -> str:
    client = qdrant_client()
    if not client or not Distance or not PointStruct or not VectorParams:
        return "Qdrant client is not configured."

    vectors = [embed_text(place_document(place)) for place in PLACES]
    dimensions = len(vectors[0])
    if not client.collection_exists(QDRANT_COLLECTION):
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=dimensions, distance=Distance.COSINE),
        )

    points = [
        PointStruct(
            id=index + 1,
            vector=vector,
            payload={
                "id": place.id,
                "name": place.name,
                "kind": place.kind,
                "station_id": place.station_id,
                "description": place.description,
            },
        )
        for index, (place, vector) in enumerate(zip(PLACES, vectors))
    ]
    client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    return f"Seeded {len(points)} places into Qdrant collection '{QDRANT_COLLECTION}'."


def qdrant_place_search(query: str, limit: int = 3) -> tuple[list[Candidate] | None, str]:
    client = qdrant_client()
    if not client:
        return None, "Qdrant is not configured; used local vector search."
    try:
        if not client.collection_exists(QDRANT_COLLECTION):
            seed_qdrant()
        query_vector = embed_text(query)
        qdrant_limit = max(limit, len(PLACES))
        if hasattr(client, "query_points"):
            response = client.query_points(
                collection_name=QDRANT_COLLECTION,
                query=query_vector,
                limit=qdrant_limit,
                with_payload=True,
            )
            points = response.points
        else:  # pragma: no cover - older qdrant-client compatibility
            points = client.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=query_vector,
                limit=qdrant_limit,
                with_payload=True,
            )
        candidates = []
        hints = semantic_hints(query)
        for point in points:
            payload = point.payload or {}
            place = place_by_id(str(payload.get("id", "")))
            if place:
                score = float(point.score) + category_adjustment(place, hints)
                candidates.append(Candidate(place=place, score=score, source="Qdrant + category rerank"))
        candidates = sorted(candidates, key=lambda item: item.score, reverse=True)[:limit]
        return candidates, f"Qdrant returned {len(candidates)} semantic matches after category rerank."
    except Exception as exc:  # pragma: no cover - depends on external service
        return None, f"Qdrant search failed ({exc}); used local vector search."


def search_places(query: str, limit: int = 3) -> tuple[list[Candidate], list[str]]:
    qdrant_candidates, message = qdrant_place_search(query, limit)
    if qdrant_candidates:
        return qdrant_candidates, [message]
    return local_place_search(query, limit), [message]


def adjacency() -> dict[str, list[tuple[str, TransitEdge]]]:
    graph: dict[str, list[tuple[str, TransitEdge]]] = {station_id: [] for station_id in STATIONS}
    for edge in TRANSIT_EDGES:
        graph[edge.a].append((edge.b, edge))
        graph[edge.b].append((edge.a, edge))
    return graph


def count_transfers(lines: list[str]) -> int:
    return sum(1 for previous, current in zip(lines, lines[1:]) if previous != current)


def local_route(start_station_id: str, target_station_id: str) -> Route | None:
    if start_station_id == target_station_id:
        return Route(
            station_ids=[start_station_id],
            station_names=[station_name(start_station_id)],
            lines=[],
            minutes=0,
            stops=0,
            transfers=0,
            source="local graph fallback",
        )

    graph = adjacency()
    queue: list[tuple[float, int, str, str | None, list[str], list[str], int, int]] = [
        (0.0, 0, start_station_id, None, [start_station_id], [], 0, 0)
    ]
    best: dict[tuple[str, str | None], float] = {}
    while queue:
        cost, minutes, station_id, previous_line, path, lines, stops, transfers = heapq.heappop(queue)
        state = (station_id, previous_line)
        if state in best and best[state] <= cost:
            continue
        best[state] = cost
        if station_id == target_station_id:
            return Route(
                station_ids=path,
                station_names=[station_name(item) for item in path],
                lines=lines,
                minutes=minutes,
                stops=stops,
                transfers=transfers,
                source="local graph fallback",
            )
        for next_station_id, edge in graph[station_id]:
            is_transfer = previous_line is not None and previous_line != edge.line
            next_transfers = transfers + (1 if is_transfer else 0)
            next_minutes = minutes + edge.minutes
            next_stops = stops + edge.stops
            transfer_penalty = 8 if is_transfer else 0
            heapq.heappush(
                queue,
                (
                    next_minutes + transfer_penalty + next_stops * 0.05,
                    next_minutes,
                    next_station_id,
                    edge.line,
                    path + [next_station_id],
                    lines + [edge.line],
                    next_stops,
                    next_transfers,
                ),
            )
    return None


def neo4j_driver():
    if not has_neo4j_config():
        return None
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    return GraphDatabase.driver(uri, auth=(user, password))


def has_neo4j_config() -> bool:
    user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
    return bool(GraphDatabase and os.getenv("NEO4J_URI") and user and os.getenv("NEO4J_PASSWORD"))


def seed_neo4j() -> str:
    driver = neo4j_driver()
    if not driver:
        return "Neo4j is not configured."
    database = os.getenv("NEO4J_DATABASE") or None
    with driver:
        with driver.session(database=database) as session:
            session.run("CREATE CONSTRAINT station_id IF NOT EXISTS FOR (s:Station) REQUIRE s.id IS UNIQUE")
            session.run("CREATE CONSTRAINT place_id IF NOT EXISTS FOR (p:Place) REQUIRE p.id IS UNIQUE")
            for station in STATIONS.values():
                session.run(
                    """
                    MERGE (s:Station {id: $id})
                    SET s.name = $name, s.aliases = $aliases
                    """,
                    id=station.id,
                    name=station.name,
                    aliases=list(station.aliases),
                )
            for place in PLACES:
                session.run(
                    """
                    MATCH (s:Station {id: $station_id})
                    MERGE (p:Place {id: $id})
                    SET p.name = $name, p.kind = $kind, p.description = $description
                    MERGE (p)-[:NEAR]->(s)
                    """,
                    id=place.id,
                    name=place.name,
                    kind=place.kind,
                    description=place.description,
                    station_id=place.station_id,
                )
            for edge in TRANSIT_EDGES:
                session.run(
                    """
                    MATCH (a:Station {id: $a}), (b:Station {id: $b})
                    MERGE (a)-[out:CONNECTS_TO {line: $line}]->(b)
                    SET out.minutes = $minutes, out.stops = $stops
                    MERGE (b)-[back:CONNECTS_TO {line: $line}]->(a)
                    SET back.minutes = $minutes, back.stops = $stops
                    """,
                    a=edge.a,
                    b=edge.b,
                    line=edge.line,
                    minutes=edge.minutes,
                    stops=edge.stops,
                )
    return f"Seeded {len(STATIONS)} stations, {len(PLACES)} places, and {len(TRANSIT_EDGES)} transit links into Neo4j."


def neo4j_route(start_station_id: str, target_station_id: str) -> tuple[Route | None, str]:
    driver = neo4j_driver()
    if not driver:
        return None, "Neo4j is not configured; used local graph routing."
    database = os.getenv("NEO4J_DATABASE") or None
    try:
        with driver:
            with driver.session(database=database) as session:
                result = session.run(
                    """
                    MATCH (start:Station {id: $start_id}), (target:Station {id: $target_id})
                    MATCH path = shortestPath((start)-[:CONNECTS_TO*..8]->(target))
                    RETURN [node IN nodes(path) | node.id] AS station_ids,
                           [node IN nodes(path) | node.name] AS station_names,
                           [rel IN relationships(path) | rel.line] AS lines,
                           [rel IN relationships(path) | rel.minutes] AS minutes,
                           [rel IN relationships(path) | rel.stops] AS stops
                    LIMIT 1
                    """,
                    start_id=start_station_id,
                    target_id=target_station_id,
                )
                record = result.single()
                if not record:
                    return None, "Neo4j found no path; used local graph routing."
                lines = list(record["lines"])
                route = Route(
                    station_ids=list(record["station_ids"]),
                    station_names=list(record["station_names"]),
                    lines=lines,
                    minutes=sum(record["minutes"]),
                    stops=sum(record["stops"]),
                    transfers=count_transfers(lines),
                    source="Neo4j shortestPath",
                )
                return route, "Neo4j calculated routes over the metro graph."
    except Exception as exc:  # pragma: no cover - depends on external service
        return None, f"Neo4j query failed ({exc}); used local graph routing."


def route_between(start_station_id: str, target_station_id: str) -> tuple[Route | None, str]:
    route, message = neo4j_route(start_station_id, target_station_id)
    if route:
        return route, message
    return local_route(start_station_id, target_station_id), message


def route_segments(route: Route) -> list[str]:
    if not route.lines:
        return []
    segments = []
    segment_line = route.lines[0]
    segment_start = route.station_names[0]
    segment_stops = 0
    for index, line in enumerate(route.lines):
        if line != segment_line:
            segments.append(f"{segment_line} from {segment_start} to {route.station_names[index]} ({segment_stops} stop{'s' if segment_stops != 1 else ''})")
            segment_line = line
            segment_start = route.station_names[index]
            segment_stops = 0
        segment_stops += 1
    segments.append(f"{segment_line} from {segment_start} to {route.station_names[-1]} ({segment_stops} stop{'s' if segment_stops != 1 else ''})")
    return segments


def describe_route(route: Route) -> str:
    if not route.lines:
        return "You are already at the closest station."
    segments = route_segments(route)
    if len(segments) == 1:
        return f"Take the {segments[0]}."
    return " Then transfer to the ".join([f"Take the {segments[0]}"] + segments[1:]) + "."


def rank_candidate(candidate: Candidate, route: Route, max_transfers: int) -> float:
    transfer_penalty = route.transfers * 0.45
    time_penalty = route.minutes * 0.015
    over_limit_penalty = 1.5 if route.transfers > max_transfers else 0
    return candidate.score - transfer_penalty - time_penalty - over_limit_penalty


def answer_user(user_text: str) -> dict[str, Any]:
    trace: list[str] = []
    intent, intent_trace = extract_intent(user_text)
    trace.extend(intent_trace)

    candidates, search_trace = search_places(intent.place_query, limit=3)
    trace.extend(search_trace)

    evaluated = []
    route_trace_added = False
    for candidate in candidates:
        route, route_trace = route_between(intent.start_station_id, candidate.place.station_id)
        if not route:
            continue
        if not route_trace_added:
            trace.append(route_trace)
            route_trace_added = True
        evaluated.append(
            {
                "candidate": candidate,
                "route": route,
                "rank": rank_candidate(candidate, route, intent.max_transfers),
            }
        )

    if not evaluated:
        return {
            "answer": "I could not find a connected route in the demo graph yet.",
            "intent": intent,
            "trace": trace,
            "evaluated": [],
        }

    evaluated.sort(key=lambda item: item["rank"], reverse=True)
    best = evaluated[0]
    place: Place = best["candidate"].place
    route: Route = best["route"]
    transfer_text = "no transfers" if route.transfers == 0 else f"{route.transfers} transfer{'s' if route.transfers != 1 else ''}"
    answer = (
        f"{place.name} is the best match. {describe_route(route)} "
        f"It is about {route.stops} stop{'s' if route.stops != 1 else ''}, "
        f"{route.minutes} minutes, with {transfer_text}. "
        f"{place.description}"
    )
    if route.transfers > intent.max_transfers:
        answer += f" Note: this is above your requested max of {intent.max_transfers} transfer(s)."

    return {
        "answer": answer,
        "intent": intent,
        "trace": trace,
        "evaluated": evaluated,
    }


def service_status() -> dict[str, str]:
    return {
        "OpenAI": "ready" if has_openai_config() else "fallback",
        "Qdrant": "ready" if has_qdrant_config() else "fallback",
        "Neo4j": "ready" if has_neo4j_config() else "fallback",
    }


def render_trace(result: dict[str, Any]) -> None:
    intent: Intent = result["intent"]
    st.caption("GraphRAG trace")
    trace_rows = [{"Step": index + 1, "Log": message} for index, message in enumerate(result["trace"])]
    st.table(trace_rows)
    st.caption("Intent")
    st.json(
        {
            "start_station": station_name(intent.start_station_id),
            "place_query": intent.place_query,
            "max_transfers": intent.max_transfers,
            "language": intent.language,
            "source": intent.source,
        },
        expanded=False,
    )
    if result["evaluated"]:
        rows = []
        for item in result["evaluated"]:
            candidate: Candidate = item["candidate"]
            route: Route = item["route"]
            rows.append(
                {
                    "Place": candidate.place.name,
                    "Closest station": station_name(candidate.place.station_id),
                    "Vector source": candidate.source,
                    "Similarity": round(candidate.score, 3),
                    "Route source": route.source,
                    "Stops": route.stops,
                    "Transfers": route.transfers,
                    "Minutes": route.minutes,
                    "Rank": round(item["rank"], 3),
                }
            )
        st.caption("Candidates")
        st.dataframe(rows, hide_index=True, width="stretch")


def render_sidebar() -> None:
    with st.sidebar:
        st.subheader("Backend")
        for name, status in service_status().items():
            st.metric(name, status)

        st.subheader("Seed")
        if st.button("Seed connected databases", width="stretch"):
            messages = []
            try:
                messages.append(seed_qdrant())
            except Exception as exc:  # pragma: no cover - external service
                messages.append(f"Qdrant seed failed: {exc}")
            try:
                messages.append(seed_neo4j())
            except Exception as exc:  # pragma: no cover - external service
                messages.append(f"Neo4j seed failed: {exc}")
            st.session_state.seed_messages = messages

        for message in st.session_state.get("seed_messages", []):
            st.caption(message)

        st.subheader("Demo prompts")
        demos = [
            "I am at Shibuya, find me a large park with few transfers.",
            "Je suis a Shinjuku, je veux visiter un temple traditionnel avec maximum un changement.",
            "渋谷駅から静かなカフェに行きたい。乗り換えは少なく。",
        ]
        for demo in demos:
            if st.button(demo, width="stretch"):
                st.session_state.pending_prompt = demo


def run_app() -> None:
    st.set_page_config(page_title="NeoTokyo Navigator", page_icon="NT", layout="wide")
    st.title("NeoTokyo Navigator")
    st.caption("GraphRAG transit assistant for Tokyo demos.")
    render_sidebar()

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Tell me where you are in Tokyo and what kind of place you want.",
                "result": None,
            }
        ]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("result"):
                render_trace(message["result"])

    prompt = st.session_state.pop("pending_prompt", None) or st.chat_input("Where are you starting, and what mood or place do you want?")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt, "result": None})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Combining vector search and graph routing..."):
                result = answer_user(prompt)
            st.write(result["answer"])
            render_trace(result)
        st.session_state.messages.append({"role": "assistant", "content": result["answer"], "result": result})


if __name__ == "__main__":
    run_app()
