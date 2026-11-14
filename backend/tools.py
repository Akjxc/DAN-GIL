"""Gemini tool declarations and the contract with backend.routing.

No pathfinding is implemented here. ToolExecutor accepts injected handlers for
tests; by default it calls the two functions in the team's routing module.
"""

import importlib
import json
import logging
from typing import Annotated, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

logger = logging.getLogger(__name__)
Text = Annotated[str, Field(min_length=1, max_length=200, strict=True)]
EdgeKind = Literal["indoorPath", "outdoorPath"]
Condition = Literal["flat", "slope", "stair", "elevator"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchPlacesArgs(StrictModel):
    query: Text


class FindRouteArgs(StrictModel):
    start_node_id: Text
    end_node_id: Text
    exclude_kinds: list[EdgeKind] = Field(default_factory=list, max_length=2)
    exclude_conditions: list[Condition] = Field(default_factory=list, max_length=4)


class Place(StrictModel):
    id: Text
    name: Text
    building_id: str | None = None
    floor: int | None = Field(default=None, strict=True)
    kind: str | None = None


class SearchResult(StrictModel):
    matches: list[Place] = Field(max_length=50)


class RouteEdge(StrictModel):
    id: Text
    from_node: Text = Field(alias="from")
    to: Text
    kind: EdgeKind
    condition: Condition


class RouteResult(StrictModel):
    status: Literal["ok", "no_route", "invalid_request"]
    nodes: list[Place] = Field(default_factory=list, max_length=1000)
    edges: list[RouteEdge] = Field(default_factory=list, max_length=1000)
    metric: Literal["hops", "distance", "time", "cost"] = "hops"
    total_cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    distance_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    duration_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_path(self):
        if self.status != "ok":
            if self.nodes or self.edges:
                raise ValueError("An unsuccessful route must have an empty path")
            return self
        if not self.nodes or len(self.edges) != len(self.nodes) - 1:
            raise ValueError("A route must contain one edge per consecutive node pair")
        for start, end, edge in zip(self.nodes, self.nodes[1:], self.edges):
            # All campus edges are bidirectional; stored orientation can differ.
            if {start.id, end.id} != {edge.from_node, edge.to}:
                raise ValueError("Route edges do not match the node sequence")
        return self


ARGUMENT_MODELS = {
    "search_places": SearchPlacesArgs,
    "find_route": FindRouteArgs,
}
DESCRIPTIONS = {
    "search_places": (
        "지도에서 장소 이름, 별칭, 층으로 실제 노드 후보를 검색합니다. "
        "출발지와 목적지는 이 도구의 결과로 확인하세요. 후보가 여러 개면 "
        "사용자가 구분할 정보를 요청하고 임의로 선택하지 마세요."
    ),
    "find_route": (
        "확인된 두 노드 사이의 양방향 경로를 계산합니다. 노드 ID는 이번 요청의 "
        "search_places 결과에서 선택해야 합니다. exclude_kinds와 "
        "exclude_conditions에 해당하는 엣지는 반드시 제외합니다. "
        "실외 거리와 실내 기본 비용에 조건별 가중치를 적용한 탐색 점수를 최소화합니다. "
        "계단을 못 쓰면 exclude_conditions에 stair를 넣으세요. "
        "경로가 없더라도 사용자의 제외 조건을 임의로 해제하지 마세요."
    ),
}
TOOL_DECLARATIONS = [
    {
        "name": name,
        "description": DESCRIPTIONS[name],
        "parameters_json_schema": model.model_json_schema(),
    }
    for name, model in ARGUMENT_MODELS.items()
]


class RoutingNotReady(Exception):
    pass


def call_routing(name: str, arguments: dict) -> dict:
    """Adapt the team's NetworkX path list to the AI's structured result."""
    try:
        module = importlib.import_module("backend.routing")
    except ModuleNotFoundError as exc:
        if exc.name == "backend.routing":
            raise RoutingNotReady from exc
        raise
    import networkx as nx

    graph = module.load_graph()
    if name == "search_places":
        return module.search_places(arguments["query"], graph=graph)
    if name != "find_route":
        raise ValueError("Unknown routing tool")
    try:
        path = module.find_route(
            graph, start=arguments["start_node_id"], end=arguments["end_node_id"],
            excluded_kinds=arguments["exclude_kinds"],
            excluded_conditions=arguments["exclude_conditions"],
        )
    except nx.NetworkXNoPath:
        # Hard exclusions must never trigger the minimal-exceptions fallback.
        return {"status": "no_route"}
    except nx.NodeNotFound:
        return {"status": "invalid_request"}
    return {
        "status": "ok", "metric": "cost",
        "total_cost": sum(
            module.base_edge_cost(graph, u, v, graph.edges[u, v])
            for u, v in zip(path, path[1:])
        ),
        "nodes": [module.place_info(graph, node_id) for node_id in path],
        "edges": [
            {key: graph.edges[u, v][key] for key in ("id", "from", "to", "kind", "condition")}
            for u, v in zip(path, path[1:])
        ],
        "distance_m": None, "duration_seconds": None,
    }


class ToolExecutor:
    """One instance per chat request; never share candidate IDs across users."""

    def __init__(self, handlers: dict[str, Callable] | None = None):
        self.handlers = handlers
        self.known_node_ids: set[str] = set()
        self.required_exclusions: tuple[set[str], set[str]] = (set(), set())

    def execute(self, name: str, arguments: dict) -> dict:
        if name not in ARGUMENT_MODELS:
            return {"status": "error", "code": "unknown_tool"}
        try:
            args = ARGUMENT_MODELS[name].model_validate(arguments)
        except ValidationError:
            return {"status": "error", "code": "invalid_arguments"}
        if name == "find_route":
            if not {args.start_node_id, args.end_node_id} <= self.known_node_ids:
                return {"status": "error", "code": "search_places_first"}
            kinds, conditions = self.required_exclusions
            if not kinds <= set(args.exclude_kinds) or not conditions <= set(args.exclude_conditions):
                return {"status": "error", "code": "constraints_changed"}
            kinds.update(args.exclude_kinds)
            conditions.update(args.exclude_conditions)
        try:
            if self.handlers is None:
                raw = call_routing(name, args.model_dump())
            else:
                handler = self.handlers.get(name)
                if handler is None:
                    raise RoutingNotReady
                raw = handler(**args.model_dump())
            if name == "search_places":
                result = SearchResult.model_validate(raw)
                self.known_node_ids.update(place.id for place in result.matches)
            else:
                result = RouteResult.model_validate(raw)
                if result.status == "ok":
                    if (result.nodes[0].id, result.nodes[-1].id) != (
                        args.start_node_id, args.end_node_id
                    ):
                        raise ValueError("Route endpoints differ from request")
                    if any(
                        e.kind in args.exclude_kinds
                        or e.condition in args.exclude_conditions
                        for e in result.edges
                    ):
                        raise ValueError("Route violates requested exclusions")
            # Ensure the provider receives JSON data, never a NetworkX object.
            return json.loads(result.model_dump_json(by_alias=True))
        except RoutingNotReady:
            return {"status": "error", "code": "routing_not_ready"}
        except (ValidationError, ValueError, TypeError):
            logger.exception("Invalid result from routing tool %s", name)
            return {"status": "error", "code": "invalid_tool_result"}
        except Exception:
            logger.exception("Routing tool %s failed", name)
            return {"status": "error", "code": "tool_failed"}
