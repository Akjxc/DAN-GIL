from fastapi import FastAPI, HTTPException

from backend.agent import AgentUnavailable, ChatRequest, ChatResponse, run_chat
from backend.tools import FindRouteArgs, call_routing
from backend.graph import load_graph
from backend.routing import place_info

app = FastAPI()


@app.get("/api/places")
def places():
    graph = load_graph()
    return [place_info(graph, node_id) for node_id, node in graph.nodes(data=True) if "name" in node]


@app.post("/api/routes")
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
