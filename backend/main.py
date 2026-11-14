from fastapi import FastAPI, HTTPException

from backend.agent import AgentUnavailable, ChatRequest, ChatResponse, run_chat
from backend.tools import FindRouteArgs, call_routing
from backend.graph import load_graph
from backend.routing import endpoint_info, is_route_endpoint, place_info

app = FastAPI()
RouteRequest = FindRouteArgs


@app.get("/api/places")
def places(endpoints_only: bool = False):
    graph = load_graph()
    if endpoints_only:
        return [endpoint_info(graph, node_id) for node_id in graph if is_route_endpoint(graph, node_id)]
    return [place_info(graph, node_id) for node_id, node in graph.nodes(data=True) if "name" in node]


@app.post("/api/routes")
def routes(request: FindRouteArgs):
    if request.has_distance_conflict:
        raise HTTPException(status_code=422, detail="거리 기준 탐색은 별도의 회피 조건을 받지 않습니다.")
    graph = load_graph()
    result = call_routing("find_route", request.model_dump(), graph=graph)
    if result["status"] == "invalid_request":
        raise HTTPException(status_code=400, detail="출발지 또는 도착지 ID가 올바르지 않습니다.")
    if result["status"] == "no_route" and request.metric == "distance":
        return {"status": "no_route", "message": "거리 정보가 있는 구간만으로 연결되지 않습니다.", "nodes": [], "edges": []}
    if result["status"] == "ok":
        path = [node["id"] for node in result["nodes"]]
        result["nodes"] = [dict(graph.nodes[node_id]) for node_id in path]
        if request.metric == "distance":
            result["edges"] = [
                {**graph.edges[u, v], "is_exception": False} for u, v in zip(path, path[1:])
            ]
            result["distance_basis"] = "registered_distance_or_endpoint_coordinates"
            return result
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
