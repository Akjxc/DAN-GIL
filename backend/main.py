import json
import os
from urllib.parse import urlsplit

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.agent import AgentUnavailable, ChatRequest, ChatResponse, run_chat
from backend.tools import FindRouteArgs, call_routing
from backend.graph import load_graph
from backend.routing import place_info

router = APIRouter()


@router.get("/api/places")
def places():
    graph = load_graph()
    return [place_info(graph, node_id) for node_id, node in graph.nodes(data=True) if "name" in node]


@router.post("/api/routes")
def routes(request: FindRouteArgs):
    graph = load_graph()
    result = call_routing("find_route", request.model_dump(), graph=graph)
    if result["status"] == "invalid_request":
        raise HTTPException(status_code=400, detail="출발지 또는 도착지 ID가 올바르지 않습니다.")
    if result["status"] == "ok":
        result["nodes"] = [dict(graph.nodes[node["id"]]) for node in result["nodes"]]
        result["cost"] = result["total_cost"]
        result["cost_basis"] = "condition_demo_cost"
    return result


@router.get("/api/health")
def health():
    return {"status": "ok"}


@router.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        return run_chat(request)
    except AgentUnavailable as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


def create_app():
    try:
        origins = json.loads(os.environ.get('CORS_ALLOWED_ORIGINS', '[]'))
        if not isinstance(origins, list):
            raise ValueError
        for origin in origins:
            if not isinstance(origin, str):
                raise ValueError
            parsed = urlsplit(origin)
            if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                    or '*' in parsed.netloc or parsed.username is not None or parsed.password is not None
                    or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
                raise ValueError
        origins = [origin.rstrip('/') for origin in origins]
    except (ValueError, TypeError) as exc:
        raise ValueError('CORS_ALLOWED_ORIGINS는 프론트 origin의 JSON 문자열 배열이어야 합니다.') from exc

    application = FastAPI()
    application.include_router(router)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=['GET', 'POST'],
        allow_headers=['Content-Type'],
    )
    return application


app = create_app()
