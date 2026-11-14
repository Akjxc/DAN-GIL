# DAN-GIL

단국대학교 죽전캠퍼스 길찾기 프로젝트야. 백엔드는 NetworkX로 경로를 계산하고, Gemini로 사용자 요청을 해석해 한국어로 안내해.

## 팀원용 로컬 테스트 (Windows)

Python 3.12 이상이 필요해. GitHub에서 저장소를 Clone하거나 이미 받았다면 `main`을 Pull하고, 저장소 폴더에서 PowerShell을 열어.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install fastapi uvicorn "networkx>=3,<4" "google-genai>=3.3,<4" "pydantic>=2,<3" "httpx>=0.27,<1"
```

팀에서 전달받은 Gemini API 키를 아래 입력창에 붙여넣어. 키는 입력 중에 가려지고 현재 PowerShell 창의 환경변수로 설정돼. 서버도 같은 창에서 실행해.

```powershell
$geminiSecret = Read-Host "Gemini API 키" -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new("", $geminiSecret).Password
Remove-Variable geminiSecret
$env:GEMINI_MODEL = "gemini-3.5-flash-lite"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

브라우저에서 [API 테스트 화면](http://127.0.0.1:8000/docs#/default/chat_api_chat_post)을 열고 `POST /api/chat` → **Try it out**을 눌러. 아래 내용을 넣고 **Execute**를 눌러.

```json
{
  "message": "정문에서 소미관 3층까지 계단 없이 가는 길 알려줘.",
  "history": []
}
```

HTTP 200과 `status: "route"`가 나오면 성공이야. `message`에서 한국어 안내를 읽고, `route.edges`에 `condition: "stair"`인 구간이 없는지 확인해.

## 오류 확인

- `ai_not_configured`가 나오면 키와 모델을 설정한 PowerShell 창에서 서버를 실행했는지 확인해.
- Gemini 오류가 계속되면 서버를 `Ctrl+C`로 중지하고, 같은 창에서 `.\.venv\Scripts\python.exe -m backend.check_gemini`를 실행해. 모델 조회, 기본 응답, 도구 명세를 포함한 응답을 차례로 확인할 수 있어.
- API 키 없이 백엔드 테스트를 실행하려면 `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`를 사용해.
- Agent 테스트 결과만 한글로 보려면 `.\.venv\Scripts\python.exe -m tests.test_agent`를 실행해.

키는 저장소와 이슈에 올리지 말고 팀원에게 비공개로 전달해. 같은 프로젝트의 키로 보낸 요청은 그 프로젝트의 사용량과 크레딧에 반영돼.

## Vercel 프론트·백엔드 연결

같은 저장소의 `main`을 기존 `dangil-api`와 `dangil-frontend` 프로젝트에 연결한다. 운영 주소는 백엔드 `https://dangil-api.vercel.app`, 프론트 `https://dangil.vercel.app`이다.

1. `dangil-api`의 Environment Variables에 `CORS_ALLOWED_ORIGINS`를 `["https://dangil.vercel.app"]`로 추가한다. 프론트 주소 뒤에 경로를 붙이지 않는다. 기존 `GEMINI_API_KEY`, `GEMINI_MODEL`은 백엔드에 유지한다.
2. `dangil-frontend`의 Environment Variables에 `VITE_API_BASE_URL`을 `https://dangil-api.vercel.app`으로 추가한다. `/api`는 붙이지 않는다. 기존 카카오 JavaScript 키도 프론트에 유지한다.
3. Production에 변수를 적용한다. Preview도 사용할 경우 해당 환경에도 API 주소를 설정하고, Preview 프론트 origin을 백엔드 허용 목록에 정확히 추가한다. 모든 `vercel.app` 주소를 허용하지 않는다.
4. 코드가 GitHub 배포 브랜치에 올라간 다음 백엔드와 프론트를 각각 재배포한다. 프론트 Root Directory는 `frontend`, 백엔드는 저장소 루트다. 프론트는 루트 `data/`도 빌드에서 접근할 수 있어야 한다.
5. 프론트에서 장소 목록·길찾기·채팅을 확인한다. 브라우저 Network에 실제 백엔드 URL이 표시되고 OPTIONS/POST가 성공해야 한다. 로그인 페이지나 HTML이 반환되면 대상 URL과 Vercel Deployment Protection을 확인한다.

프론트 빌드에는 `VITE_API_BASE_URL`이 필수다. 환경변수를 바꾸면 다시 빌드·배포해야 한다. `VITE_` 값은 브라우저에 공개되므로 Gemini 키를 프론트 변수에 넣지 않는다. CORS 설정은 브라우저의 응답 읽기 허용 정책이며 API 인증을 대신하지 않는다. 설정이 없으면 서버는 실행되지만 다른 도메인에서 읽는 요청은 허용하지 않는다.

로컬 개발에서는 `VITE_API_BASE_URL`을 비워 두고 Vite의 `/api` 프록시를 사용한다. 이 경우 별도 CORS 설정 없이 기존처럼 로컬 백엔드에 연결된다. 프론트 테스트는 `cd frontend` 후 `npm test`, 백엔드는 기존 unittest 명령으로 실행한다. 두 프로젝트는 별도 배포되므로 운영 배포의 커밋과 Ready 상태를 각각 확인한다.
