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

키는 저장소와 이슈에 올리지 말고 팀원에게 비공개로 전달해. 같은 프로젝트의 키로 보낸 요청은 그 프로젝트의 사용량과 크레딧에 반영돼.
