import json
from pathlib import Path

import networkx as nx


def load_graph():
    """ 데이터 위치의 json을 읽어 모두 그래프에 등록하고, 이를 반환하는 함수.
    
    from backend.graph import load_graph
    graph = load_graph()
    """
    # data 폴더 위치 지정
    DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

    # 모든 json 파일의 내용 담음
    documents = []

    for file_path in sorted(DEFAULT_DATA_DIR.glob("*.json")):
        with file_path.open(encoding="utf-8-sig") as file:
            documents.append(json.load(file))

    # 양방향 그래프 생성
    graph = nx.Graph()

    # 모든 파일의 노드, 엣지 등록
    # document.get("nodes", []): nodes를 가져오되, 키가 없으면 빈 목록을 사용합니다. 
    # 현재 내용이 {}인 파일도 처리할 수 있습니다.
    for document in documents:
        for node in document.get("nodes", []): 
            graph.add_node(node["id"], **node)

    for document in documents:
        for edge in document.get("edges", []):
            graph.add_edge(edge["from"], edge["to"], **edge)
    # 노드를 전부 등록한 다음 간선을 등록하는 이유는, 건물 내부의 간선이 다른 JSON에 정의된 출입구 노드를 연결할 수 있기 때문입니다.

    # 완성한 그래프 호출한 곳으로 반환
    return graph

# 이 파일을 직접 실행했을 때만 아래 확인 코드 실행.
# 다른 파일에서 가져올 때는 실행하지 않음.
if __name__ == "__main__":
    graph = load_graph()

    print("전체 노드: ", graph.number_of_nodes())
    print("전체 엣지: ", graph.number_of_edges())

    print("정문->정문분기점: ", graph.has_edge("mainGate", "mainGateJc"))
    print("정문분기점->정문: ", graph.has_edge("mainGateJc", "mainGate"))

    print(
        "제3공학관 4층 복도 등록 여부:",
        "engineering3F4Hall" in graph
    )