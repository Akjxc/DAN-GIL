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
    metric: Literal["cost", "distance", "indoor_priority"] = Field(
        default="cost", description="최단거리는 distance, 실내 우선은 indoor_priority, 일반 길찾기는 cost."
    )
    exclude_kinds: list[EdgeKind] = Field(default_factory=list, max_length=2)
    exclude_conditions: list[Condition] = Field(default_factory=list, max_length=4)
    allow_exceptions: bool = Field(default=False, strict=True, description="조건을 만족하는 길이 없을 때만 예외 구간을 최소화한 대안을 허용합니다.")

    @property
    def has_distance_conflict(self) -> bool:
        return self.metric == "distance" and bool(
            self.exclude_kinds or self.exclude_conditions or self.allow_exceptions
        )


class Place(StrictModel):
    id: Text
    name: Text
    building_id: str | None = None
    floor: int | None = Field(default=None, strict=True)
    kind: str | None = None


class SearchResult(StrictModel):
    matches: list[Place] = Field(max_length=50)
    alternative_entrances: list[Place] = Field(default_factory=list, max_length=50)


class RouteEdge(StrictModel):
    id: Text
    from_node: Text = Field(alias="from")
    to: Text
    kind: EdgeKind
    condition: Condition
    is_exception: bool = False


class RouteResult(StrictModel):
    status: Literal["ok", "no_route", "invalid_request"]
    nodes: list[Place] = Field(default_factory=list, max_length=1000)
    edges: list[RouteEdge] = Field(default_factory=list, max_length=1000)
    metric: Literal["hops", "distance", "time", "cost", "indoor_priority"] = "hops"
    total_cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    distance_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    outdoor_distance_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    duration_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    exception_notice: str | None = None

    @model_validator(mode="after")
    def check_path(self):
        if self.status != "ok":
            if self.nodes or self.edges or self.exception_notice:
                raise ValueError("An unsuccessful route must have an empty path")
            return self
        if not self.nodes or len(self.edges) != len(self.nodes) - 1:
            raise ValueError("A route must contain one edge per consecutive node pair")
        if bool(self.exception_notice) != any(edge.is_exception for edge in self.edges):
            raise ValueError("The exception notice must match the marked segments")
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
        "지도에서 선택 가능한 출입구와 주요 장소를 이름, 별칭, 층으로 검색합니다. "
        "건물과 층을 입력하면 해당 층의 출입구 후보를 찾습니다. "
        "출발지와 목적지는 이 도구의 결과로 확인하세요. 후보가 여러 개면 "
        "사용자가 구분할 정보를 요청하고 임의로 선택하지 마세요."
    ),
    "find_route": (
        "확인된 두 노드 사이의 양방향 경로를 계산합니다. 노드 ID는 이번 요청의 "
        "search_places 결과에서 선택해야 합니다. exclude_kinds와 "
        "exclude_conditions에 해당하는 엣지는 먼저 제외합니다. "
        "최단거리나 가장 짧은 길을 요청하면 metric=distance를 사용합니다. "
        "실내 위주 요청에는 metric=indoor_priority를 사용합니다. 실외 거리 합을 최소화하며 명시한 제외 조건은 모두 지킵니다. "
        "단순한 실내 우선 요청에서는 실외를 exclude_kinds에 넣지 않고 allow_exceptions는 false로 설정하세요. "
        "거리 기준과 회피 조건을 함께 요청하면 사용자가 어느 쪽을 우선할지 질문하세요. "
        "metric=cost는 실외 거리와 실내 기본 비용에 조건별 가중치를 적용합니다. "
        "계단을 못 쓰면 exclude_conditions에 stair를 넣으세요. "
        "'계단만 빼줘', '되도록 피하고 싶어'처럼 회피를 원하면 allow_exceptions를 true로 설정하세요. "
        "'계단은 못 써', '절대 포함하지 마' 같은 필수 조건이나 휠체어 요청이면 false로 설정하세요. "
        "제외 목록을 지우지 마세요. 대안이 가능하면 서버가 예외 구간을 최소화합니다."
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


def exception_notice(edges, excluded_kinds, excluded_conditions):
    kind_labels = {"indoorPath": "실내", "outdoorPath": "실외"}
    condition_labels = {"flat": "평지", "slope": "경사", "stair": "계단", "elevator": "엘리베이터"}
    exclusions = [("kind", value, kind_labels[value]) for value in sorted(set(excluded_kinds))]
    exclusions += [("condition", value, condition_labels[value]) for value in sorted(set(excluded_conditions))]
    included = []
    for field, value, label in exclusions:
        count = sum(edge[field] == value for edge in edges)
        if count:
            included.append(f"{label} 구간 {count}개")
    labels = "·".join(label for _, _, label in exclusions)
    total = sum(edge["is_exception"] for edge in edges)
    breakdown = f" ({', '.join(included)})" if len(included) > 1 else ""
    segments = f"예외 구간 {total}개{breakdown}" if len(included) > 1 else included[0]
    return f"{labels} 구간을 모두 제외하면 가능한 경로가 없어서, 대안 경로에 {segments}를 포함했어요."


def call_routing(name: str, arguments: dict, *, graph=None) -> dict:
    """Adapt the team's NetworkX path list to the AI's structured result."""
    try:
        module = importlib.import_module("backend.routing")
    except ModuleNotFoundError as exc:
        if exc.name == "backend.routing":
            raise RoutingNotReady from exc
        raise
    import networkx as nx

    if graph is None:
        graph = module.load_graph()
    if name == "search_places":
        return module.search_places(arguments["query"], graph=graph, endpoints_only=True)
    if name != "find_route":
        raise ValueError("Unknown routing tool")
    excluded_kinds = arguments["exclude_kinds"]
    excluded_conditions = arguments["exclude_conditions"]
    metric = arguments.get("metric", "cost")
    route_args = {
        "start": arguments["start_node_id"], "end": arguments["end_node_id"],
        "excluded_kinds": excluded_kinds, "excluded_conditions": excluded_conditions,
    }
    distance_m = outdoor_distance_m = None
    try:
        if metric == "distance":
            path, distance_m = module.find_distance_route(graph, route_args["start"], route_args["end"])
        elif metric == "indoor_priority":
            path, outdoor_distance_m = module.find_indoor_priority_route(graph, **route_args)
        else:
            try:
                path = module.find_route(graph, **route_args)
            except nx.NetworkXNoPath:
                if not arguments.get("allow_exceptions", False) or not (excluded_kinds or excluded_conditions):
                    raise
                path = module.find_route_with_minimal_exceptions(graph, **route_args)
    except nx.NetworkXNoPath:
        return {"status": "no_route", "metric": "distance"} if metric == "distance" else {"status": "no_route"}
    except nx.NodeNotFound:
        return {"status": "invalid_request"}
    exception_kinds = ["outdoorPath"] if metric == "indoor_priority" else excluded_kinds
    exception_conditions = [] if metric == "indoor_priority" else excluded_conditions
    edges = []
    for u, v in zip(path, path[1:]):
        edge = {key: graph.edges[u, v][key] for key in ("id", "from", "to", "kind", "condition")}
        edge["is_exception"] = edge["kind"] in exception_kinds or edge["condition"] in exception_conditions
        edges.append(edge)
    return {
        "status": "ok", "metric": metric,
        "total_cost": sum(
            module.base_edge_cost(graph, u, v, graph.edges[u, v])
            for u, v in zip(path, path[1:])
        ) if metric != "distance" else None,
        "nodes": [module.place_info(graph, node_id) for node_id in path],
        "edges": edges,
        "exception_notice": (exception_notice(edges, exception_kinds, exception_conditions)
                             if any(edge["is_exception"] for edge in edges) else None),
        "distance_m": distance_m, "outdoor_distance_m": outdoor_distance_m, "duration_seconds": None,
    }


class ToolExecutor:
    """One instance per chat request; never share candidate IDs across users."""

    def __init__(self, handlers: dict[str, Callable] | None = None):
        self.handlers = handlers
        self.known_node_ids: set[str] = set()
        self.required_exclusions: tuple[set[str], set[str]] = (set(), set())
        self.allow_exceptions: bool | None = None

    def execute(self, name: str, arguments: dict) -> dict:
        if name not in ARGUMENT_MODELS:
            return {"status": "error", "code": "unknown_tool"}
        try:
            args = ARGUMENT_MODELS[name].model_validate(arguments)
        except ValidationError:
            return {"status": "error", "code": "invalid_arguments"}
        if name == "find_route":
            if args.has_distance_conflict:
                return {"status": "error", "code": "distance_with_exclusions"}
            if not {args.start_node_id, args.end_node_id} <= self.known_node_ids:
                return {"status": "error", "code": "search_places_first"}
            kinds, conditions = self.required_exclusions
            if (not kinds <= set(args.exclude_kinds) or not conditions <= set(args.exclude_conditions)
                    or (self.allow_exceptions is False and args.allow_exceptions)):
                return {"status": "error", "code": "constraints_changed"}
            self.allow_exceptions = args.allow_exceptions
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
                    for edge in result.edges:
                        excluded = edge.kind in args.exclude_kinds or edge.condition in args.exclude_conditions
                        indoor_priority = args.metric == "indoor_priority"
                        exception = edge.kind == "outdoorPath" if indoor_priority else excluded
                        if exception != edge.is_exception or (excluded and (indoor_priority or not args.allow_exceptions)):
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
