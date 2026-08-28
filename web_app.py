from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import app as navigator


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PROMPT = "I am at Shibuya. Find a quiet traditional place with max 1 transfer."
DEMO_PROMPTS = [
    "I am at Shibuya, find me a large park with few transfers.",
    "Je suis a Shinjuku, je veux visiter un temple traditionnel avec maximum un changement.",
    "渋谷駅から静かなカフェに行きたい。乗り換えは少なく。",
]

STATION_POINTS: dict[str, tuple[int, int]] = {
    "shibuya": (118, 330),
    "harajuku": (270, 245),
    "yoyogi": (398, 195),
    "shinjuku": (548, 112),
    "shinjuku_gyoemmae": (615, 176),
    "asakusa": (468, 322),
}

PLACE_OFFSETS: dict[str, tuple[int, int]] = {
    "yoyogi_park": (0, -50),
    "shinjuku_gyoen": (34, 34),
    "meiji_shrine": (48, -45),
    "sensoji_temple": (78, -35),
    "blue_bottle_shibuya": (-42, -42),
}

LINE_COLORS = {
    "JR Yamanote Line": "#e5483f",
    "Tokyo Metro Ginza Line": "#11a9b6",
    "Tokyo Metro Marunouchi Line": "#d9a21b",
}


app = FastAPI(title="NeoTokyo Navigator")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def station_point(station_id: str) -> dict[str, Any]:
    x, y = STATION_POINTS[station_id]
    station = navigator.STATIONS[station_id]
    return {"id": station_id, "name": station.name, "x": x, "y": y}


def place_point(place: navigator.Place) -> dict[str, Any]:
    station_x, station_y = STATION_POINTS[place.station_id]
    offset_x, offset_y = PLACE_OFFSETS.get(place.id, (32, -32))
    return {
        "id": place.id,
        "name": place.name,
        "kind": place.kind,
        "x": station_x + offset_x,
        "y": station_y + offset_y,
    }


def line_key(line: str) -> str:
    return line.replace("Tokyo Metro ", "").replace("JR ", "")


def map_edges() -> list[dict[str, Any]]:
    edges = []
    for edge in navigator.TRANSIT_EDGES:
        x1, y1 = STATION_POINTS[edge.a]
        x2, y2 = STATION_POINTS[edge.b]
        edges.append(
            {
                "a": edge.a,
                "b": edge.b,
                "line": edge.line,
                "label": line_key(edge.line),
                "minutes": edge.minutes,
                "stops": edge.stops,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "color": LINE_COLORS.get(edge.line, "#8a7fd6"),
            }
        )
    return edges


def route_points(route: navigator.Route | None) -> str:
    if not route:
        return ""
    points = []
    for station_id in route.station_ids:
        x, y = STATION_POINTS[station_id]
        points.append(f"{x},{y}")
    return " ".join(points)


def result_view(result: dict[str, Any]) -> dict[str, Any]:
    intent: navigator.Intent = result["intent"]
    evaluated = []

    for item in result["evaluated"]:
        candidate: navigator.Candidate = item["candidate"]
        route: navigator.Route = item["route"]
        evaluated.append(
            {
                "place": candidate.place,
                "place_point": place_point(candidate.place),
                "station": navigator.station_name(candidate.place.station_id),
                "score": round(candidate.score, 3),
                "rank": round(item["rank"], 3),
                "route": route,
                "segments": navigator.route_segments(route),
                "over_limit": route.transfers > intent.max_transfers,
            }
        )

    best = evaluated[0] if evaluated else None
    route = best["route"] if best else None
    active_station_ids = set(route.station_ids if route else [])
    active_place_id = best["place"].id if best else None

    return {
        "answer": result["answer"],
        "intent": {
            "start_station": navigator.station_name(intent.start_station_id),
            "place_query": intent.place_query,
            "max_transfers": intent.max_transfers,
            "language": intent.language,
            "source": intent.source,
        },
        "trace": result["trace"],
        "evaluated": evaluated,
        "best": best,
        "route": route,
        "route_points": route_points(route),
        "active_station_ids": active_station_ids,
        "active_place_id": active_place_id,
    }


def base_context(
    request: Request,
    prompt: str = DEFAULT_PROMPT,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "request": request,
        "prompt": prompt,
        "error": error,
        "status": navigator.service_status(),
        "demo_prompts": DEMO_PROMPTS,
        "stations": [station_point(station_id) for station_id in navigator.STATIONS],
        "places": [place_point(place) for place in navigator.PLACES],
        "map_edges": map_edges(),
        "line_legend": [
            {"line": line, "label": line_key(line), "color": color}
            for line, color in LINE_COLORS.items()
        ],
        "result": result_view(result) if result else None,
    }


def run_navigation(prompt: str) -> dict[str, Any]:
    return navigator.answer_user(prompt)


def response_template(request: Request) -> str:
    if request.headers.get("HX-Request"):
        return "partials/navigator.html"
    return "index.html"


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    result = run_navigation(DEFAULT_PROMPT)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=base_context(request, prompt=DEFAULT_PROMPT, result=result),
    )


@app.post("/navigate", response_class=HTMLResponse)
def navigate(request: Request, prompt: str = Form("")) -> HTMLResponse:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        return templates.TemplateResponse(
            request=request,
            name=response_template(request),
            context=base_context(request, prompt=prompt, error="Add a starting station and a vibe."),
        )

    result = run_navigation(cleaned_prompt)
    return templates.TemplateResponse(
        request=request,
        name=response_template(request),
        context=base_context(request, prompt=cleaned_prompt, result=result),
    )


@app.post("/seed", response_class=HTMLResponse)
def seed(request: Request) -> HTMLResponse:
    messages = []
    try:
        messages.append(navigator.seed_qdrant())
    except Exception as exc:  # pragma: no cover - depends on external service
        messages.append(f"Qdrant seed failed: {exc}")
    try:
        messages.append(navigator.seed_neo4j())
    except Exception as exc:  # pragma: no cover - depends on external service
        messages.append(f"Neo4j seed failed: {exc}")

    return templates.TemplateResponse(
        request=request,
        name="partials/status.html",
        context={
            "request": request,
            "status": navigator.service_status(),
            "seed_messages": messages,
        },
    )
