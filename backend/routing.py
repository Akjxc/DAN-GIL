import networkx as nx

from backend.graph import load_graph

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

    # 출발지부터 도착지까지 방문하는 노드 ID 목록 반환
    return nx.shortest_path(
        filtered_graph,
        source=start,
        target=end
    )

# 조건을 위반하는 예외 구간을 최소화하는 경로 탐색 함수
# 기준 1. 제외 조건을 어기는 구간이 가장 적은 경로
# 기준 2. 예외 구간 수가 같다면 전체 이동 구간이 가장 적은 경로
# 기존 함수는 제외 조건에 해당하는 엣지를 탐색에서 제거. 
# 해당 함수는 해당 엣지를 이용할 수 있게 두되, 예외 비용을 부여
def find_route_with_minimal_exceptions(graph, start, end, excluded_conditions=None, excluded_kinds=None):
    if excluded_kinds is None:
        excluded_kinds = []
    if excluded_conditions is None:
        excluded_conditions = []

    penalty = graph.number_of_nodes()

    def edge_cost(u, v, edge):
        violates_kind = (
            edge["kind"] in excluded_kinds
        )
        violates_condition = (
            edge["condition"] in excluded_conditions
        )

        # 예외 구간 비용: 1 + penalty
        # penalty는 예외 구간 수를 먼저 최소화하기 위한 값
        # 노드를 반복 방문하지 않는 경로의 이동 구간은 최대 N-1
        # 따라서 예외 한번에 N점을 추가하면 길이를 줄이려고 예외를 하나 더 사용하는 경로가 선택되지 않음
        # 같은 간선이 kind와 condition 모두 위반해도 예외 구간 1개로 간주 
        if violates_kind or violates_condition:
            return 1 + penalty

        # 일반 구간 비용: 1
        return 1 

    return nx.shortest_path(
        graph,
        source=start,
        target=end,
        weight=edge_cost
    )

if __name__ == "__main__":
    # graph.py에서 만든 함수로 지도 그래프를 불러옴
    graph = load_graph()

    excluded_kinds = []
    excluded_conditions = ["slope"]
    
    try:
        path = find_route(
            graph,
            start="mainGate",
            end="engineering1F5Hall",
            excluded_kinds=excluded_kinds,
            excluded_conditions=excluded_conditions
        )

        print("경로: ", path)
        print("이동 구간 수: ", len(path) - 1)
        # 예를 들어 path가 ["A", "B", "C"]라면 A→B→C로 이동
        # 노드는 3개지만 이동 구간은 2개이므로 len(path) - 1로 구간 수를 계산

        print("경로에 사용된 구간 조건:")
        # zip(path, path[1:])는 경로에서 연속한 두 노드씩 꺼내는 표현
        for u, v in zip(path, path[1:]):
            edge = graph.edges[u, v]
            print(u, "->", v, "|", edge["kind"], "|", edge["condition"])

    except nx.NetworkXNoPath:
        print("예외 구간 최소화 함수 호출")
        path = find_route_with_minimal_exceptions(
            graph,
            start="mainGate",
            end="engineering1F5Hall",
            excluded_kinds=excluded_kinds,
            excluded_conditions=excluded_conditions
        )
        print("경로:", path)

        exception_count = 0

        for u, v in zip(path, path[1:]):
            edge = graph.edges[u, v]

            is_exception = (
                edge["condition"] in excluded_conditions
                or edge["kind"] in excluded_kinds
                )

            if is_exception:
                exception_count += 1

            print(
                u, "→", v,
                "|", edge["kind"],
                "|", edge["condition"],
                "| 예외:", is_exception,
            )
        print("예외 구간 수:", exception_count)
        print("전체 이동 구간 수:", len(path) - 1)
    except nx.NodeNotFound:
        print("출발지 또는 목적지 ID 찾을 수 없음")