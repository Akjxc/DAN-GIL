import math
import re
from heapq import heappop, heappush
from itertools import count

import networkx as nx

from backend.graph import load_graph


EARTH_RADIUS_M = 6_371_000
OUTDOOR_METERS_PER_POINT = 10.0
INDOOR_BASE_COST = 1.0

CONDITION_COSTS = {
    "flat": 1,
    "slope": 3,
    "stair": 5,
    "elevator": 1,
}

KIND_MULTIPLIERS = {
    "indoorPath": 1,
    "outdoorPath": 10,
}

LANDMARK_LABELS = {
    "mainGate": None,
    "bearStatue": None,
    "parkingJc": "주차빌딩 앞",
    "labJc": "종합실험동 앞",
    "hyeDangYardJc": "노천마당 앞",
    "dentalJc": "치과대학 방면",
}


def outdoor_distance_m(graph, u, v):
    """위도·경도의 Haversine 거리(m). 길의 굴곡이나 높이는 반영하지 않음."""
    coordinates = []
    for node_id in (u, v):
        node = graph.nodes[node_id]
        latitude = node.get("latitude")
        longitude = node.get("longitude")
        if (
            type(latitude) not in (int, float)
            or type(longitude) not in (int, float)
            or not math.isfinite(latitude)
            or not math.isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise ValueError(f"실외 노드 {node_id!r}의 위도·경도를 확인해주세요.")
        coordinates.append((math.radians(latitude), math.radians(longitude)))

    (lat1, lon1), (lat2, lon2) = coordinates
    haversine = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    # 부동소수점 오차로 asin의 입력이 범위를 벗어나지 않도록 제한.
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, max(0.0, haversine))))


def base_edge_cost(graph, u, v, edge):
    """실외는 10m당 1점, 실내는 기본 1점에 조건·실내외 가중치를 적용.

    실내 엣지의 base_cost로 가중치를 곱하기 전 기본 점수를 보정할 수 있음.
    반환값은 탐색 점수이며, 실내 좌표나 거리 정보는 필요하지 않음.
    """
    kind = edge["kind"]
    if kind == "outdoorPath":
        base_cost = outdoor_distance_m(graph, u, v) / OUTDOOR_METERS_PER_POINT
    elif kind == "indoorPath":
        base_cost = edge.get("base_cost", INDOOR_BASE_COST)
        if type(base_cost) not in (int, float) or not math.isfinite(base_cost) or base_cost <= 0:
            raise ValueError(f"실내 엣지 {u!r} → {v!r}의 base_cost는 유한한 양수여야 합니다.")
    else:
        raise ValueError(f"지원하지 않는 엣지 kind: {kind!r}")

    return base_cost * CONDITION_COSTS[edge["condition"]] * KIND_MULTIPLIERS[kind]


BUILDING_ALIASES = {
    "softwareMedia": ["소미관", "소프트웨어관", "소프트웨어ICT관", "미디어관", "미디어센터", "소프트웨어/미디어관"],
    "engineering1": ["제1공학관", "1공학관"],
    "engineering2": ["제2공학관", "2공학관"],
    "engineering3": ["제3공학관", "3공학관"],
    "library": ["도서관", "퇴계기념중앙도서관", "중앙도서관"],
    "social": ["사회과학관", "사과관"],
    "humanity": ["인문관"], "business": ["상경관"],
    "education": ["사범관"], "hyeDang": ["혜당관", "학생회관"],
    "lawGraduate": ["법학관", "대학원동", "법학관/대학원동"],
    "beomJung": ["범정관"], "international": ["국제관"],
}


def find_distance_route(graph, start, end):
    """Minimize known distances; never substitute a demo cost for missing meters.

    Explicit distance_m (or distance) takes precedence. Otherwise use the
    endpoint coordinate distance. Edges with neither are excluded.
    """
    if start not in graph or end not in graph:
        raise nx.NodeNotFound("Unknown route endpoint")
    measured_graph = nx.Graph()
    measured_graph.add_nodes_from(graph.nodes)
    for u, v, edge in graph.edges(data=True):
        value = edge.get("distance_m", edge.get("distance"))
        if type(value) in (int, float) and math.isfinite(value) and value >= 0:
            meters = value
        else:
            try:
                meters = outdoor_distance_m(graph, u, v)
            except ValueError:
                continue
        measured_graph.add_edge(u, v, distance_m=meters)
    path = nx.shortest_path(measured_graph, start, end, weight="distance_m")
    total = sum(measured_graph.edges[u, v]["distance_m"] for u, v in zip(path, path[1:]))
    return path, total


def place_info(graph, node_id):
    """Return only fields accepted by the AI interface."""
    node = graph.nodes[node_id]
    return {"id": node_id, "name": node["name"],
            "building_id": node.get("buildingId"), "floor": node.get("floor"),
            "kind": node.get("kind")}


def is_route_endpoint(graph, node_id):
    node = graph.nodes[node_id]
    return "name" in node and (node.get("kind") == "entrance" or node_id in LANDMARK_LABELS)


def endpoint_info(graph, node_id):
    place = place_info(graph, node_id)
    place["name"] = LANDMARK_LABELS.get(node_id) or place["name"]
    return place


def search_places(query, graph=None, *, endpoints_only=False):
    """Search IDs, names, building aliases and floors; keep ambiguous candidates.

    A specified floor without a facility kind targets that floor's hall.
    A building without a floor returns its entrances for user clarification.
    """
    if graph is None:
        graph = load_graph()
    normalize = lambda value: re.sub(r"\s+", "", value).casefold()
    text = normalize(query)
    if not text:
        return {"matches": []}
    if endpoints_only:
        if any(text == normalize(node_id) and not is_route_endpoint(graph, node_id) for node_id in graph):
            return {"matches": []}
        graph = graph.subgraph(node_id for node_id in graph if is_route_endpoint(graph, node_id))
    info = endpoint_info if endpoints_only else place_info
    exact = [i for i, n in graph.nodes(data=True)
             if text in (normalize(i), normalize(n.get("name", "")))
             or (endpoints_only and text == normalize(LANDMARK_LABELS.get(i) or ""))]
    if exact:
        return {"matches": [info(graph, i) for i in exact[:50]]}
    if text in {"정문", "단국대정문", "단국대학교정문"} and "mainGate" in graph:
        return {"matches": [info(graph, "mainGate")]}
    # Do not silently turn an unmapped classroom into a building entrance.
    if re.search(r"\d+호", text):
        return {"matches": []}
    floor_match = re.search(r"(지하|b)?(-?\d+)층", text)
    floor = None
    if floor_match:
        floor = int(floor_match.group(2))
        if floor_match.group(1):
            floor = -abs(floor)
    kind = next((value for word, value in [
        ("엘리베이터", "elevator"), ("엘베", "elevator"), ("계단", "stair"),
        ("복도", "hall"), ("출입구", "entrance"), ("입구", "entrance"),
    ] if word in text), None)
    hits = [(len(normalize(alias)), bid) for bid, aliases in BUILDING_ALIASES.items()
            for alias in [bid, *aliases] if normalize(alias) in text]
    longest = max((length for length, _ in hits), default=0)
    buildings = {bid for length, bid in hits if length == longest}
    if not buildings and text.startswith("공학관"):
        buildings = {"engineering1", "engineering2", "engineering3"}
    matches = []
    for node_id, node in graph.nodes(data=True):
        if buildings:
            if node.get("buildingId") not in buildings:
                continue
            if floor is not None and node.get("floor") != floor:
                continue
            target_kind = kind or ("hall" if floor is not None and not endpoints_only else "entrance")
            if node.get("kind") != target_kind:
                continue
        elif text not in normalize(node.get("name", "")) and not (
            endpoints_only and text in normalize(LANDMARK_LABELS.get(node_id) or "")
        ):
            continue
        matches.append(info(graph, node_id))
    if endpoints_only and not matches and floor is not None and buildings and kind in (None, "entrance"):
        alternatives = [
            info(graph, node_id) for node_id, node in graph.nodes(data=True)
            if node.get("buildingId") in buildings and node.get("kind") == "entrance"
        ]
        if alternatives:
            return {"matches": [], "alternative_entrances": sorted(alternatives, key=lambda n: (
                n["building_id"], n["floor"] is None, n["floor"] or 0, n["name"],
            ))[:50]}
    return {"matches": sorted(matches, key=lambda n: n["id"])[:50]}

def find_route(graph, start, end, excluded_kinds=None, excluded_conditions=None):
    #제외 조건을 전달하지 않으면 빈 목록 사용
    if excluded_kinds is None:
        excluded_kinds = []
    if excluded_conditions is None:
        excluded_conditions = []

    # 전달받은 제외 조건으로 각 엣지 사용 여부 판단
    def allow_edge(u, v):
        edge = graph.edges[u, v]

        kind_allowed = (
            edge["kind"] not in excluded_kinds
        )
        condition_allowed = (
            edge["condition"] not in excluded_conditions
        )
        return kind_allowed and condition_allowed
        # 실내외 조건, 구간 조건이 모두 허용될 때만 해당 엣지 사용

    # excluded_conditions에 해당되는 condition의 edge가 보이지 않는 그래프 생성
    filtered_graph = nx.subgraph_view(
        graph,
        filter_edge=allow_edge
    )

    def edge_cost(u, v, edge):
        return base_edge_cost(graph, u, v, edge)

    # 출발지부터 도착지까지 방문하는 노드 ID 목록 반환
    return nx.shortest_path(
        filtered_graph,
        source=start,
        target=end,
        weight=edge_cost,
    )

# 조건을 위반하는 예외 구간을 최소화하는 경로 탐색 함수
# 기준 1. 제외 조건을 어기는 구간이 가장 적은 경로
# 기준 2. 예외 구간 수가 같다면 기본 비용 합이 가장 작은 경로
# 기존 함수는 제외 조건에 해당하는 엣지를 탐색에서 제거. 
# 해당 함수는 해당 엣지를 이용할 수 있게 두되, 예외 비용을 부여
def find_route_with_minimal_exceptions(graph, start, end, excluded_conditions=None, excluded_kinds=None):
    if excluded_kinds is None:
        excluded_kinds = []
    if excluded_conditions is None:
        excluded_conditions = []

    max_base_cost = max(
        (base_edge_cost(graph, u, v, edge) for u, v, edge in graph.edges(data=True)),
        default=0,
    )
    # 기본 비용이 음수가 아니므로 최적 경로 중 노드를 반복 방문하지 않는 경로가 존재.
    # 예외 한 번의 벌점을 모든 단순 경로의 기본 비용 상한보다 크게 설정.
    penalty = (graph.number_of_nodes() - 1) * max_base_cost + 1

    def edge_cost(u, v, edge):
        base_cost = base_edge_cost(graph, u, v, edge)
        violates_kind = (
            edge["kind"] in excluded_kinds
        )
        violates_condition = (
            edge["condition"] in excluded_conditions
        )

        # 같은 간선이 kind와 condition을 모두 위반해도 예외 구간 1개로 간주.
        if violates_kind or violates_condition:
            return base_cost + penalty

        return base_cost

    return nx.shortest_path(
        graph,
        source=start,
        target=end,
        weight=edge_cost
    )

def find_indoor_priority_route(graph, start, end, excluded_kinds=None, excluded_conditions=None):
    """Prefer an indoor-only route, otherwise minimize outdoor meters then total cost."""
    kinds = set(excluded_kinds or ())
    conditions = set(excluded_conditions or ())
    try:
        path = find_route(graph, start, end, kinds | {"outdoorPath"}, conditions)
        return path, 0.0
    except nx.NetworkXNoPath:
        if "outdoorPath" in kinds:
            raise

    # Dijkstra orders routes by (outdoor meters, total cost).
    order = count()
    best = {start: (0.0, 0.0)}
    previous = {}
    pending = [(best[start], next(order), start)]
    while pending:
        score, _, node = heappop(pending)
        if score != best[node]:
            continue
        if node == end:
            path = [end]
            while path[-1] != start:
                path.append(previous[path[-1]])
            return path[::-1], score[0]
        for neighbor, edge in graph[node].items():
            if edge["kind"] in kinds or edge["condition"] in conditions:
                continue
            meters = outdoor_distance_m(graph, node, neighbor) if edge["kind"] == "outdoorPath" else 0.0
            cost = base_edge_cost(graph, node, neighbor, edge)
            candidate = (score[0] + meters, score[1] + cost)
            if neighbor not in best or candidate < best[neighbor]:
                best[neighbor] = candidate
                previous[neighbor] = node
                heappush(pending, (candidate, next(order), neighbor))
    raise nx.NetworkXNoPath(f"No path from {start} to {end}")


if __name__ == "__main__":
    graph = load_graph()
    start = "mainGate"
    end = "bearStatue"
    excluded_kinds = ["indoorPath"]
    excluded_conditions = []

    try:
        try:
            path = find_route(
                graph, start, end,
                excluded_kinds=excluded_kinds,
                excluded_conditions=excluded_conditions,
            )
        except nx.NetworkXNoPath:
            print("설정한 제외 조건을 모두 지키는 경로가 없습니다.")
            approval = input(
                f"kind={excluded_kinds}, condition={excluded_conditions} 조건의 "
                "예외 구간을 최소화해서 다시 찾을까요? (y/n): "
            ).strip().casefold()
            path = None
            if approval == "y":
                path = find_route_with_minimal_exceptions(
                    graph, start, end,
                    excluded_kinds=excluded_kinds,
                    excluded_conditions=excluded_conditions,
                )
            else:
                print("재탐색을 취소했습니다.")

        if path is not None:
            print("경로:", path)
            print("이동 구간 수:", len(path) - 1)
            total_base_cost = 0
            exception_count = 0

            for u, v in zip(path, path[1:]):
                edge = graph.edges[u, v]
                base_cost = base_edge_cost(graph, u, v, edge)
                is_exception = (
                    edge["condition"] in excluded_conditions
                    or edge["kind"] in excluded_kinds
                )
                total_base_cost += base_cost
                exception_count += int(is_exception)
                print(
                    u, "→", v,
                    "|", edge["kind"], "|", edge["condition"],
                    "| 탐색 점수:", f"{base_cost:.2f}", "| 예외:", is_exception,
                )

            print("예외 구간 수:", exception_count)
            print("총 탐색 점수:", f"{total_base_cost:.2f}")
    except nx.NetworkXNoPath:
        print("예외를 허용해도 목적지까지 연결되는 경로가 없습니다.")
    except nx.NodeNotFound:
        print("출발지 또는 목적지 ID 찾을 수 없음")
