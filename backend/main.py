from fastapi import FastAPI, HTTPException
from typing import Literal
import networkx as nx

from backend.agent import AgentUnavailable, ChatRequest, ChatResponse, run_chat
from backend.tools import FindRouteArgs, call_routing
from backend.graph import load_graph
from backend.routing import place_info, find_distance_route

app = FastAPI()


class RouteRequest(FindRouteArgs):
    metric: Literal["cost", "distance"] = "cost"


@app.get("/api/places")
def places():
    graph = load_graph()
    return [place_info(graph, node_id) for node_id, node in graph.nodes(data=True) if "name" in node]


@app.post("/api/routes")
def routes(request: RouteRequest):
    graph = load_graph()
    if request.metric == "distance":
        if request.exclude_kinds or request.exclude_conditions or request.allow_exceptions:
            raise HTTPException(status_code=422, detail="거리 기준 탐색은 별도의 회피 조건을 받지 않습니다.")
        try:
            path, total = find_distance_route(graph, request.start_node_id, request.end_node_id)
        except nx.NodeNotFound:
            raise HTTPException(status_code=400, detail="출발지 또는 도착지 ID가 올바르지 않습니다.")
        except nx.NetworkXNoPath:
            return {"status": "no_route", "message": "거리 정보가 있는 구간만으로 연결되지 않습니다.", "nodes": [], "edges": []}
        return {
            "status": "ok", "metric": "distance", "distance_m": total,
            "distance_basis": "registered_distance_or_endpoint_coordinates",
            "nodes": [dict(graph.nodes[n]) for n in path],
            "edges": [{**graph.edges[u, v], "is_exception": False} for u, v in zip(path, path[1:])],
            "total_cost": None, "duration_seconds": None,
        }
    result = call_routing("find_route", request.model_dump(), graph=graph)
    if result["status"] == "invalid_request":
        raise HTTPException(status_code=400, detail="출발지 또는 도착지 ID가 올바르지 않습니다.")
    if result["status"] == "ok":
        result["nodes"] = [dict(graph.nodes[node["id"]]) for node in result["nodes"]]
        result["cost"] = result["total_cost"]
        result["cost_basis"] = "condition_demo_cost"
    return result


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        return run_chat(request)
    except AgentUnavailable as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
