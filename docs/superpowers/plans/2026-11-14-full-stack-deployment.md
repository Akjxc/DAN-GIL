# DAN-GIL Vercel 프론트·백엔드 분리 배포 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 현재 요청은 계획 작성만이며 구현·설정 변경·배포를 수행하지 않는다.

**Goal:** 기존 프론트 Vercel 프로젝트와 새 백엔드 Vercel 프로젝트를 연결해, 로컬 서버 없이 팀원이 완성된 기능을 확인하고 main 변경을 자동 배포한다.

**Architecture:** 같은 GitHub 저장소를 두 Vercel 프로젝트에 연결한다. React 브라우저 앱이 환경변수로 지정된 FastAPI HTTPS 주소를 직접 호출한다. FastAPI의 CORS 허용 목록으로 프론트 출처를 명시한다. 두 프로젝트는 각각 빌드·배포·롤백한다.

**Tech Stack:** React/Vite, Python 3.12, FastAPI/CORSMiddleware, NetworkX, Google GenAI, Vercel, GitHub Actions.

**Spec:** 사용자 요구는 계획만 작성, 무료 우선, 첫 접속 지연 허용, 프론트·백엔드를 각각 Vercel에 배포하는 것이다. 아래 설정과 실행 순서는 이 요구에 대한 제안이다. 이전 문서의 Vercel Services 단일 프로젝트 제안은 이 계획으로 대체한다.

## Global Constraints

- 기존 프론트 프로젝트와 운영 주소를 유지하고 같은 저장소에 연결된 백엔드 프로젝트를 추가한다. 저장소를 둘로 나눌 필요는 없다.
- 두 프로젝트의 Production Branch는 main이다. 프로젝트별 배포 완료 시점은 다르며 원자적 배포가 아니다.
- 무료 사용 범위에서 시작하고 유료 플랜·자동 과금을 활성화하지 않는다. Gemini 무료 할당량은 호스팅과 별도로 확인한다.
- 실시간은 push → 빌드·배포 → 공유 주소 새로고침을 의미한다. 로컬 파일 저장 즉시 원격 반영이나 브라우저 자동 갱신은 별도 기능이다.
- API 경로 `/api/health`, `/api/routes`, `/api/chat`와 정상 응답 계약은 유지한다.
- JSON 데이터는 저장소에 포함해 배포한다. 현재 별도 DB나 상시 실행 VM은 필요하지 않다.
- 미커밋 `backend/routing.py` 변경을 덮어쓰지 않는다. 모든 실제 수정·테스트·배포는 후속 구현 단계에서 한다.

## 현재 상태와 선행 확인

2026-11-14 로컬 코드 기준으로 프론트는 `/api/routes`, `/api/chat` 상대 URL을 사용한다. `frontend/vite.config.js`에는 로컬 8000 포트로 향하는 개발 프록시만 있다. `backend/main.py`에는 위 세 엔드포인트가 있고 CORS 미들웨어는 없다. 루트 `app.py`는 `backend.main.app`을 노출한다.

`backend/graph.py`는 루트 `data/*.json`을 읽고, `frontend/src/campusGraph.js`는 `../../data/campus.json`을 import한다. 루트의 `pyproject.toml`과 `uv.lock`, 프론트의 `package-lock.json`을 재사용한다.

현재 `base_edge_cost(graph, u, v, edge)`를 `backend/main.py`에서 인자 3개로 호출하는 불일치가 남아 있다. `backend/tools.py`는 올바르게 계산한 `total_cost`를 이미 반환한다. 배포 전에 HTTP 테스트로 재현하고 중복 계산을 제거할 계획이다. 현재 점수 설명도 실제 계산 기준에 맞춰야 한다.

이전 실행 검증은 기존 `.venv`가 가리키는 Python 실행 파일이 없어 진행하지 못했다. API 실행 성공·오류 재현·배포 성공은 아직 확인하지 않았다. 실제 Vercel 프로젝트 설정, 도메인, 권한도 조회하지 않았다.

## 연결 방식 결정

| 방식 | 특성 | 선택 |
| --- | --- | --- |
| 브라우저 → 백엔드 URL 직접 호출 | API URL 환경변수와 CORS 설정 필요. API 요청을 백엔드 로그에서 직접 확인 가능 | 이번 계획의 기본안 |
| 프론트 `/api` → 외부 rewrite → 백엔드 | 기존 상대 URL 유지 가능. 외부 프록시 시간 제한과 Preview 대상 연결을 관리해야 함 | 이번 계획에서는 사용하지 않음 |

직접 호출 방식은 기존 90초 채팅 제한과 최대 6회의 AI 호출 시간을 조정할 때 외부 rewrite 제한을 별도로 고려하지 않아도 된다. 외부 rewrite의 현재 문서상 제한은 120초이며, 백엔드 함수 maxDuration을 늘려도 이 제한이 함께 늘어나지 않는다. [Vercel 프록시 제한](https://vercel.com/docs/limits).

## 프로젝트 설정

프로젝트명과 URL은 예시이며 구현 시 실제 발급된 고정 운영 주소를 기록한다. 경로는 GitHub 저장소 루트인 `DAN-GIL/` 기준이다.

| 항목 | 프론트 프로젝트 | 백엔드 프로젝트 |
| --- | --- | --- |
| 프로젝트명 예시 | 기존 프로젝트 유지 | `dan-gil-api` |
| Git 저장소 | 같은 저장소 | 같은 저장소 |
| Production Branch | main | main |
| Root Directory | `frontend` | 저장소 루트 `.` |
| Framework Preset | Vite | FastAPI |
| Install | `npm ci` | pyproject.toml + uv.lock 기반 기본 Python 설치 |
| Build | `npm run build` | FastAPI 기본값 |
| Output Directory | `dist` | 기본값 유지, dist 지정하지 않음 |
| 진입점 | Vite index.html | 루트 `app.py`의 app |
| 런타임 | Node.js 22.x 빌드 | Python 3.12 |
| 설정 파일 | 필요 시 `frontend/vercel.json` | 루트 `vercel.json`, `.python-version` |

백엔드 Root Directory를 `backend`로 지정하면 현재 루트의 의존성·app.py·data 및 `backend.*` import 구조와 맞지 않는다. 루트 `.`로 배포하고 프레임워크를 FastAPI로 명시한다. Vercel은 지원 위치의 app 인스턴스를 감지해 Python 함수로 실행하므로 Uvicorn 상시 서버용 Start Command는 넣지 않는다. [FastAPI 배포](https://vercel.com/docs/frameworks/backend/fastapi).

프론트는 `data/campus.json` 접근을 위해 “Include source files outside of the Root Directory in the Build Step” 설정을 확인한다. `frontend` 아래 코드만 복사해서 빌드하면 안 된다. [공용 소스 접근](https://vercel.com/docs/monorepos/monorepo-faq).

## 환경변수 계약

| 프로젝트 | 이름 | 값/용도 |
| --- | --- | --- |
| 프론트 Production | `VITE_API_BASE_URL` | 실제 백엔드 고정 운영 origin, 예: `https://dan-gil-api.vercel.app` |
| 프론트 | `VITE_KAKAO_MAP_KEY` | 카카오 JavaScript 키 |
| 백엔드 | `GEMINI_API_KEY` | 서버 전용 Gemini 키 |
| 백엔드 | `GEMINI_MODEL` | 계정에서 무료 할당량과 함수 호출이 확인된 모델 |
| 백엔드 | `CORS_ALLOWED_ORIGINS` | JSON 문자열 배열: 실제 프론트 운영 origin과 명시적으로 사용하는 Preview origin |

`VITE_API_BASE_URL`에는 `/api`를 붙이지 않는다. 실제 요청은 `<base>/api/routes`와 `<base>/api/chat`가 된다. 프론트 환경변수는 빌드 시 반영되므로 변경 후 재배포한다. `VITE_` 값은 브라우저에 공개되며 Gemini 키와 Vercel 보호 우회 비밀값은 넣지 않는다. [Vite 환경변수](https://vite.dev/guide/env-and-mode).

## Review Focus

- URL 결합 오류·환경변수 누락: Task 3에서 /api 중복, 끝 슬래시, 잘못된 배포 URL을 검증한다.
- CORS preflight 실패·오류 응답의 CORS 헤더 누락: Task 2에서 허용/비허용 origin과 400/422/503 응답을 검증한다.
- 공용 JSON 누락·API 인자 불일치: Task 1·4에서 실제 경로와 프론트 빌드를 검증한다.
- Preview 보호 페이지를 API 응답으로 받는 상황: Task 4에서 비로그인 브라우저의 OPTIONS/POST와 Content-Type을 확인한다.
- 두 프로젝트의 버전 불일치·한쪽만 롤백: Task 5에서 커밋 쌍과 호환성을 기록한다.

## Task 1: 백엔드 API 응답 검증 및 선행 오류 정리

**Files:** Modify `backend/main.py`, `frontend/src/CampusExperience.jsx`; Create `tests/test_api.py`.

**Interfaces:** routes 입력은 기존 start_node_id/end_node_id/exclude_conditions/exclude_kinds를 유지한다. 성공 응답의 `cost`는 `total_cost`와 동일하며 좌표 포함 nodes, edges를 유지한다.

- [ ] 유효한 Python 3.12 환경을 준비하고 잠금 파일 기반으로 의존성을 설치한다. 기존 사용자의 가상환경은 임의로 덮어쓰지 않는다.
- [ ] HTTP 테스트로 mainGate → softwareMediaF3Hall, 계단 제외 요청의 현재 실패를 확인한다. 수정 후 200/ok, 양 끝 ID 일치, stair 없음, cost == total_cost가 되어야 한다.
- [ ] `backend/main.py`의 중복 점수 재계산 대신 tools가 반환한 total_cost를 사용한다. 화면의 점수 안내를 실제 기준과 맞춘다. routing 알고리즘은 바꾸지 않는다.
- [ ] 같은 장소는 점수 0/엣지 0, 없는 노드는 400, indoor/outdoor 모두 제외하면 no_route, 잘못된 입력은 422를 검증한다.
- [ ] `python -m unittest discover -s tests -v`가 통과해야 다음 단계로 간다.

## Task 2: 백엔드 독립 배포와 CORS

**Files:** Create `.python-version`, `vercel.json`, `tests/test_cors.py`; Modify `backend/main.py`.

**Interfaces:** CORS_ALLOWED_ORIGINS는 origin 문자열의 JSON 배열이다. 배포에서는 프론트 HTTPS origin을 정확히 등록하고 로컬 직접 호출이 필요할 때만 localhost:5173을 추가한다.

- [ ] 루트 vercel.json에 FastAPI 설정과 app.py 함수 maxDuration 180초를 선언하고 Python 3.12를 선택한다. Fluid Compute 및 유효한 설정 적용을 확인한다.
- [ ] Python 함수에서 frontend/node_modules, .venv, tests, docs 등 불필요한 파일을 제외하되 app.py/backend/data와 런타임 패키지를 포함한다. 프론트 빌드용 파일 자체를 저장소에서 제거하지 않는다.
- [ ] CORSMiddleware는 정확한 origin 목록, GET/POST 메서드, Content-Type 헤더, allow_credentials=False로 설정한다. OPTIONS preflight는 미들웨어가 처리한다. 현재 쿠키 인증은 없으므로 credentials를 추가하지 않는다.
- [ ] 허용 origin의 OPTIONS가 성공하고 Access-Control-Allow-Origin이 해당 origin인지 확인한다. 비허용 origin에는 허용 헤더가 없어야 한다. 400/422/503 JSON 오류에도 허용 origin의 CORS 헤더가 있어야 한다.
- [ ] CORS는 브라우저의 읽기 권한 정책이며 API 인증/사용량 차단 기능이 아니라는 점을 운영 문서에 명시한다. [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/).
- [ ] 같은 GitHub 저장소로 새 Vercel 프로젝트를 만들고 Root Directory `.`와 FastAPI를 선택한다. Gemini 변수와 CORS 목록을 입력하고 백엔드를 먼저 배포한다.
- [ ] 고정 운영 URL의 /api/health와 /api/routes를 확인하고 실제 Gemini 질문은 별도 수동 점검한다. 익명 브라우저 요청을 Vercel 로그인 페이지로 보내는 Deployment Protection 설정이 있는지 확인한다.

## Task 3: 프론트 API 주소와 오류 처리 통일

**Files:** Create `frontend/src/services/apiClient.js`, `frontend/src/services/apiClient.test.js`, `frontend/src/services/chatService.test.js`, `frontend/src/services/routeService.test.js`; Modify `frontend/src/services/chatService.js`, `frontend/src/services/routeService.js`, `frontend/vite.config.js`, `backend/agent.py`, `tests/test_agent.py`.

**Interfaces:** `buildApiUrl(baseUrl: string, path: string): string`는 base의 끝 슬래시를 제거하고 `/api/...` path를 결합한다. `apiUrl(path: string): string`는 import.meta.env.VITE_API_BASE_URL을 사용한다. 기존 sendChatMessage/requestRoute 호출 형태는 유지한다.

- [ ] URL 결합 테스트를 먼저 작성한다: 빈 base는 /api/routes, HTTPS base와 끝 슬래시가 있는 base 모두 정확히 한 개의 슬래시로 결합된다. 배포용 base는 path/query/fragment가 없는 HTTPS origin이어야 한다.
- [ ] 두 서비스의 fetch 주소를 공통 apiUrl 함수로 교체한다. 로컬 개발에서는 빈 base를 허용해 기존 Vite /api 프록시를 유지한다.
- [ ] 프론트 build 시 VITE_API_BASE_URL 누락·잘못된 origin은 명확한 오류로 종료한다. CI의 빌드 검사에서는 `https://api.example.invalid` 같은 테스트용 origin을 명시한다. 배포 설정 누락을 조용히 상대 주소로 대체하지 않는다.
- [ ] 채팅 대기를 190,000ms로 조정하고 서버 함수 제한 180초와 맞춘다. SDK 호출별 20초/최대 6회 제한은 유지하고 SDK 자동 재시도는 끈다. 이 숫자를 실제 전체 처리 시간의 엄밀한 상한으로 설명하지 않는다.
- [ ] 상태 코드/Content-Type을 검사해 429, 503, HTML 504, 네트워크/CORS 실패를 사용자용 문구로 변환한다. POST는 자동 재전송하지 않는다. 브라우저가 CORS와 네트워크 실패를 구분해 주지 않는 경우 로그/Network로 조사한다.
- [ ] Node 내장 테스트 러너로 위 세 테스트 파일을 실행한다. fetch/타이머를 대체해 외부 호출 없이 시간 초과, 취소, 타이머 정리, 단일 POST 전송을 검증한다.

## Task 4: 프론트 배포 및 공유 환경 검증

**Files:** Update `README.md`; 필요한 프론트 전용 설정만 `frontend/vercel.json`에 둔다.

- [ ] 기존 프론트 프로젝트의 Root Directory frontend, Vite, npm ci/build/dist 설정을 확인하고 공용 data 접근을 활성화한다.
- [ ] VITE_API_BASE_URL에 Task 2의 백엔드 고정 운영 주소를 입력하고 프론트를 재배포한다. Gemini 키는 프론트 프로젝트에 등록하지 않는다.
- [ ] 카카오 키의 허용 도메인에 실제 프론트 운영 주소와 사용할 고정 Preview 주소를 등록한다. 백엔드 도메인은 지도 표시 origin이 아니다.
- [ ] 브라우저 Network에서 백엔드 도메인으로 향하는 OPTIONS와 POST가 성공하는지 확인한다. 응답은 JSON이어야 하며 로그인 화면/HTML이면 보호 설정과 대상을 조사한다.
- [ ] 지도/실제 경로/계단 제외/같은 장소/AI 채팅을 팀원 PC·모바일에서 확인한다. 모든 로컬 서버를 꺼도 동작해야 한다.
- [ ] 프론트 번들에 Gemini 키가 포함되지 않았는지 확인하고 현재 무료 사용량과 모델 한도를 기록한다.

## Task 5: 자동 배포, Preview, 버전 관리

**Files:** Create `.github/workflows/ci.yml`, `docs/deployment.md`.

- [ ] 두 프로젝트의 Production Branch를 main으로 설정한다. 같은 저장소 push는 연결된 각 프로젝트의 별도 배포를 만들 수 있으며 한쪽 실패가 다른 쪽 성공을 취소하지 않는다. [Vercel 모노레포](https://vercel.com/docs/monorepos).
- [ ] CI는 Python 3.12/Node.js 22.x에서 `uv sync --frozen`, `uv run --frozen python -m unittest discover -s tests -v`, 프론트 서비스 테스트, `npm --prefix frontend ci`, `npm --prefix frontend run build`를 수행한다. 빌드용 API origin을 명시하고 Gemini 실키 없이 실행한다.
- [ ] 가능한 경우 CI 성공을 main 병합 조건으로 지정한다. 초기에는 frontend/backend/data 각각의 변경으로 필요한 배포가 실행되는지 확인하고 경로별 skip 최적화는 뒤로 미룬다.
- [ ] 1차 공유 환경은 main 프론트 + main 백엔드다. 두 배포의 Ready 상태와 커밋 SHA를 확인한 뒤 팀에 해당 버전을 사용하도록 안내한다. 개발 PC에서 저장만 한 변경은 배포되지 않는다.
- [ ] 프론트 Preview는 초기에는 main 백엔드를 명시적으로 사용한다. 이 조합은 UI 검토용이며 변경된 백엔드까지 검증했다고 판단하지 않는다. Preview origin은 백엔드 CORS에 정확히 등록한다.
- [ ] 백엔드 변경을 병합 전에 함께 검증할 때는 해당 백엔드 배포 URL을 프론트 작업 브랜치의 Preview 변수에 지정해 재빌드하고, 프론트 Preview origin을 백엔드 Preview CORS에 등록한다. 양쪽 같은 SHA를 확인한다. 브랜치 전용 변수 override 지원 여부를 확인하고 지원되지 않으면 검증 대상 하나를 정해 Preview 변수를 수동 전환한다.
- [ ] 보호된 backend Preview는 단순 CORS로 접근되지 않는다. 팀 정책상 허용되는 공개 테스트 API 구성 또는 서버 측 인증 프록시를 선택해 검증해야 한다. 보호 우회 토큰을 VITE_ 변수에 넣지 않는다. 미해결 상태를 통합 Preview 성공으로 처리하지 않는다.
- [ ] 브랜치별 통합 검증을 자주 하게 되면 Related Projects로 대상 URL 선택을 자동화하는 후속 작업을 고려한다. 이 기능만으로 CORS와 Deployment Protection까지 해결되는 것은 아니다. [Related Projects](https://vercel.com/docs/monorepos).
- [ ] API 변경은 새 백엔드가 이전 프론트 요청도 처리하도록 추가부터 적용하고 필드 제거는 프론트 전환 이후에 한다. JSON 노드 ID 변경도 같은 호환성 원칙을 적용한다.
- [ ] 정상 프론트 배포 ID + 백엔드 배포 ID + SHA를 쌍으로 기록한다. 장애 시 호환되는 쌍으로 각각 롤백한다. 환경변수·CORS 대시보드 설정은 별도로 복구한다.

## 완료 기준

- [ ] 기존 프론트 주소와 새 백엔드 고정 주소가 각각 동작한다.
- [ ] 로컬 서버 없이 프론트에서 실제 경로와 AI 채팅을 사용할 수 있다.
- [ ] API 요청이 올바른 백엔드로 가고 CORS preflight가 성공한다.
- [ ] main 변경 후 두 프로젝트의 배포 완료와 커밋을 확인할 수 있다.
- [ ] Preview가 사용하는 백엔드 버전을 명확히 알 수 있다.
- [ ] 무료 사용 범위, 오류 안내, 두 프로젝트 복구 방법이 기록되어 있다.

## 계획 검토 상태

2026-11-14에 사용자 결정에 맞춰 계획 문서만 수정했다. 단일 Services 설정과 Render 대안은 실행 계획에서 제외했다. 실제 코드, Vercel 프로젝트, 환경변수, 배포는 변경하지 않았다. 코드·설정 검증은 위 실행 단계에서 수행한다.
