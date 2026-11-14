# Gemini 길찾기 연결

## 현재 구현 범위

- `backend/tools.py`: 두 도구의 명세, 입력/결과 검증, `routing.py` 연결 지점.
- `backend/agent.py`: Gemini 응답 → 허용된 함수 실행 → 결과 전달 → 자연어 안내.
- `backend/main.py`: `POST /api/chat`. 기존 `/api/health` 유지.
- `tests/test_agent.py`: 실제 SDK 데이터 형식과 가짜 Gemini/길찾기를 사용하는 오프라인 테스트.

팀원의 `routing.py`에 연결되어 실제 JSON 지도에서 경로를 계산한다.
`search_places`를 추가했고, 기존 `find_route(graph, start, end, ...)`의 반환 목록은
`tools.py`에서 장소·엣지 정보로 변환한다. `graph.py`와 지도 JSON은 수정하지 않는다.
제외 조건을 만족하는 경로가 없으면 `no_route`를 반환하며 예외 허용 함수를 자동 호출하지 않는다.

## 실행 (PowerShell, 저장소 루트)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install fastapi uvicorn "networkx>=3,<4" "google-genai>=3.3,<4" "pydantic>=2,<3" "httpx>=0.27,<1"
$env:GEMINI_API_KEY = "AI Studio에서 발급한 키"
$env:GEMINI_MODEL = "계정에서 사용 가능한 함수 호출 지원 모델 ID"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

키와 모델은 서버 환경변수로 설정한다. `.env`를 자동으로 읽지는 않는다.
키를 프런트엔드, GitHub 또는 채팅에 붙여넣지 않는다.
모델 기본값은 고정하지 않았다. AI Studio에서 무료 제공 여부와 실제 호출 한도를 확인한다.

- API 키: https://aistudio.google.com/apikey
- 모델/가격: https://ai.google.dev/gemini-api/docs/pricing
- 함수 호출: https://ai.google.dev/gemini-api/docs/function-calling
- Python SDK: https://googleapis.github.io/python-genai/

브라우저에서 `http://127.0.0.1:8000/docs`를 열어 `/api/chat`을 테스트한다.

```json
{
  "message": "정문에서 소미관 3층까지 계단 없이 가고 싶어",
  "history": []
}
```

후속 요청에는 이전 사용자 메시지와 안내문을 `history`에 전달한다.
역할은 `user` 또는 `assistant`만 허용한다. 최근 20개 메시지까지 지원한다.
서버에 대화 세션을 저장하지 않으며, 이전 안내를 실제 경로 결과로 재사용하지 않는다.
각 요청에서 장소와 경로를 다시 확인한다.

응답 필드:

| 필드 | 설명 |
| --- | --- |
| `status` | `reply`: 대화/추가 질문, `route`: 경로 성공, `no_route`: 조건에 맞는 경로 없음, `error`: 처리 오류 |
| `message` | 화면에 표시할 한국어 안내 |
| `route` | 검증된 길찾기 결과. 경로가 없거나 오류면 `null` |
| `error_code` | 처리 오류의 코드. 정상 응답은 `null` |

입력 오류는 HTTP 422, 설정 누락은 503, Gemini 한도 초과는 429다.
HTTP 오류 본문은 `detail.code`, `detail.message` 형식이다.
프런트엔드는 지도 경로를 `route.nodes`와 `route.edges`로 표시한다.
`message`에서 노드나 좌표를 추출하지 않는다. 좌표는 별도의 지도 데이터와 매칭한다.
프런트엔드 연결 및 배포 환경의 프록시/CORS 설정은 별도 작업이다.

## routing.py와 AI 도구의 연결

AI에 공개한 `find_route(start_node_id, end_node_id, exclude_kinds, exclude_conditions)`를
`tools.py`의 `call_routing()`이 아래 실제 함수에 맞게 변환한다.
현재는 도구 실행마다 JSON 지도를 읽어 그래프를 만들며 공유 그래프를 변경하지 않는다.
층을 지정하면 기본 목적지 후보는 그 층의 복도이고, 건물만 지정하면 출입구 후보를 반환한다.
여러 후보가 있으면 AI가 사용자에게 확인한다. 별칭은 `BUILDING_ALIASES`에서 관리한다.

```python
def search_places(query: str, graph=None) -> dict:
    ...

def find_route(
    graph,
    start: str,
    end: str,
    excluded_kinds=None,
    excluded_conditions=None,
) -> list[str]:
    ...
```

`search_places` 반환 예시:

```json
{
  "matches": [
    {
      "id": "softwareMediaF3Hall",
      "name": "소프트웨어/미디어관 3층 복도",
      "building_id": "softwareMedia",
      "floor": 3,
      "kind": "hall"
    }
  ]
}
```

- 후보 없음: `{"matches": []}`. 최대 후보 수는 50개.
- `id`, `name`은 필수. 나머지 필드는 선택.
- 지도 JSON의 `buildingId`는 반환할 때 `building_id`로 변환한다.
- 모호한 건물 이름은 실제 노드 후보들을 반환하고 임의의 층/출입구를 확정하지 않는다.
- AI는 이번 요청의 검색 결과에 있는 ID만 길찾기에 사용할 수 있다.

실제 `routing.find_route`는 노드 ID 목록을 반환한다. 아래는 연결부에서 변환한
AI 도구의 성공 반환 형식이다 (A/B는 형식 설명용 가상 노드).

```json
{
  "status": "ok",
  "nodes": [
    {"id": "A", "name": "출발 장소", "floor": 1},
    {"id": "B", "name": "도착 장소", "floor": 1}
  ],
  "edges": [
    {"id": "AtoB", "from": "A", "to": "B", "kind": "indoorPath", "condition": "flat"}
  ],
  "metric": "hops",
  "distance_m": null,
  "duration_seconds": null
}
```

- `nodes`와 `edges`는 실제 이동 순서로 반환한다. 같은 출발지/목적지는 노드 1개, 엣지 0개.
- 모든 길은 양방향이므로 엣지의 `from`/`to` 저장 방향은 이동 방향과 달라도 된다.
- 엣지 반환 필드는 위 예시에 맞춘다. 원본의 `name` 등 추가 필드는 변환 시 제외한다.
- `exclude_kinds`: `indoorPath`, `outdoorPath`.
- `exclude_conditions`: `flat`, `slope`, `stair`, `elevator`.
- 제외 조건은 OR로 적용한다. 하나라도 해당하는 엣지를 사용하면 안 된다.
- 제외 목록은 그래프의 복사본/뷰에 적용하고 공유 원본 그래프를 변경하지 않는다.
- 경로 없음: `{"status": "no_route"}`. 노드 없음 등 잘못된 요청: `{"status": "invalid_request"}`.
- 연결부가 NetworkX의 경로 없음/노드 없음 예외를 위 결과로 변환한다. AI에 `print()`나 예외 객체를 전달하지 않는다.
- 거리가 없으면 `metric=hops`로 표시한다. 거리/시간을 임의로 계산하지 않는다.
- 거리·시간 기준을 도입하면 `metric=distance` 또는 `time`으로 명시한다.

## 현재 제한과 검증

### 실제 API 오류 진단

키와 모델을 설정했던 PowerShell에서 서버를 `Ctrl+C`로 중지하고 실행한다.

```powershell
.\.venv\Scripts\python.exe -m backend.check_gemini
```

모델 목록에서 설정한 ID가 반환되는지 확인한 뒤, 기본 요청과 운영 코드와 동일한 도구 명세를 포함한 요청을 각각 한 번 실행한다. 각 단계의 성공 여부와 오류 사유를 한글로 표시한다.
키와 원본 오류 본문은 출력하지 않는다. 모델 목록에 있다는 사실만으로 무료 사용량이 보장되지는 않는다.
진단 호출 제한은 각각 60초이며 SDK 재시도는 꺼져 있다. 운영 서버의 20초 설정은 변경하지 않는다.
둘 다 실패하면 모델/서비스/계정 쪽을 추가 확인하고, 기본 호출만 성공하면 도구 설정을 조사한다.
둘 다 성공해도 호출 시간이 20초를 넘었다면 운영 제한 시간 조정을 검토한다.
진단 후 같은 창에서 아래 명령으로 서버를 재실행한다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Gemini 호출은 요청당 최대 6회, 함수 실행은 최대 12회로 제한한다.
등록되지 않은 함수 실행, 미검색 ID, 잘못된 조건, 경로 끝점 불일치,
제외 조건을 위반한 경로는 차단한다. 한 요청 안에서 이미 적용한 제외 조건을
모델이 풀어 재호출하는 것도 차단한다. 다른 사용자 요청과 검색 결과를 공유하지 않는다.

자연어에서 조건을 올바르게 추출하는지, 질문이 충분한지, 안내문이 경로에 충실한지는
실제 Gemini와 연결한 뒤 별도 평가해야 한다. 프롬프트만으로 정확성을 보장할 수 없다.
API 키 없는 테스트는 네트워크 호출 없이 도구 실행 흐름과 오류 처리를 검증한다.

```powershell
.\.venv\Scripts\python.exe -m pip install "httpx>=0.27,<1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

실제 연결 후 확인할 대화:

1. 정문 → 소미관 3층, 계단 제외.
2. 출발지 없이 '도서관으로 가줘' → 출발지 질문.
3. '공학관으로 가줘' → 건물/출발지 확인.
4. 조건을 만족하는 경로 없음 → 조건 유지, 대체 경로 조작 없음.
5. '그럼 출발지는 정문이야' → 대화 맥락 유지 후 재검색.
