"""키와 모델을 설정한 PowerShell 창에서 Gemini 연결을 진단합니다."""

import argparse
import os
import time

import httpx
from google import genai
from google.genai import errors, types

from backend.agent import generation_config


def format_api_error(code: int) -> str:
    reason = {
        400: "Gemini가 요청을 거부했습니다. 모델 설정이나 요청 형식을 확인해 주세요.",
        401: "인증에 실패했습니다. API 키 설정을 확인해 주세요.",
        403: "접근이 거부됐습니다. 키와 프로젝트 권한을 확인해 주세요.",
        404: "요청한 모델 또는 리소스를 찾지 못했습니다.",
        429: "사용량 한도에 도달했습니다. 프로젝트의 한도를 확인해 주세요.",
        504: "Gemini가 요청 처리 시간 초과를 반환했습니다.",
    }.get(code, "Gemini API에서 오류를 반환했습니다.")
    return f"실패 (HTTP {code}) — {reason}"


def run_checks(client, model: str) -> int:
    print(f"선택한 모델: {model}", flush=True)
    print("[1/3] 모델 목록 조회 중…", flush=True)
    try:
        models = list(client.models.list())
    except errors.APIError as exc:
        print(f"[1/3] 모델 목록 조회 {format_api_error(exc.code)}", flush=True)
        return 1
    available = {m.name.removeprefix("models/"): m for m in models if m.name}
    selected = model.removeprefix("models/")
    if selected not in available:
        print("[1/3] 모델 확인 실패 — API가 반환한 목록에 설정한 모델이 없습니다.")
        print("목록에서 확인된 Flash 모델 (무료 한도는 AI Studio에서 별도 확인):")
        for name, item in sorted(available.items()):
            if "flash" in name and "generateContent" in (item.supported_actions or []):
                print(f"  {name}")
        return 1
    print("[1/3] 모델 목록 조회 성공 — 설정한 모델을 찾았습니다.", flush=True)
    failed = False
    for label, config in [
        ("[2/3] 기본 요청 (도구 없이)", types.GenerateContentConfig()),
        ("[3/3] 도구 명세 포함 요청", generation_config()),
    ]:
        started = time.monotonic()
        print(f"{label} 전송 중…", flush=True)
        try:
            response = client.models.generate_content(
                model=model, contents="Hello. Reply with a short greeting.", config=config
            )
            candidate = (response.candidates or [None])[0]
            parts = candidate.content.parts if candidate and candidate.content else []
            text = any(p.text and not p.thought for p in (parts or []))
            calls = sum(p.function_call is not None for p in (parts or []))
            if text or calls:
                received = []
                if text:
                    received.append("텍스트 응답 수신")
                if calls:
                    received.append(f"함수 호출 요청 {calls}건 수신")
                outcome = "성공 — " + ", ".join(received)
            else:
                outcome = "실패 — 응답에 텍스트나 함수 호출 요청이 없습니다."
                failed = True
        except errors.APIError as exc:
            outcome = format_api_error(exc.code)
            failed = True
        except httpx.TimeoutException:
            outcome = "실패 — 응답 대기 시간이 초과됐습니다."
            failed = True
        except httpx.TransportError:
            outcome = "실패 — Gemini API에 연결하지 못했습니다."
            failed = True
        print(f"{label} {outcome} (소요 시간 {time.monotonic() - started:.1f}초)", flush=True)
    return int(failed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=60, choices=range(1, 121), metavar="초",
                        help="요청당 응답 대기 시간 (기본 60초)")
    args = parser.parse_args()
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "").strip()
    if not key or not model:
        print("이 PowerShell 창에서 GEMINI_API_KEY와 GEMINI_MODEL을 먼저 설정해 주세요.")
        return 1
    print(f"Gemini SDK 버전 {genai.__version__} | 요청당 최대 {args.timeout}초 대기 | 자동 재시도 꺼짐", flush=True)
    try:
        with genai.Client(api_key=key, http_options=types.HttpOptions(
            timeout=args.timeout * 1000,
            retry_options=types.HttpRetryOptions(attempts=1),
        )) as client:
            return run_checks(client, model)
    except httpx.TimeoutException:
        print("[1/3] 모델 목록 조회 실패 — 응답 대기 시간이 초과됐습니다.")
        return 1
    except httpx.TransportError:
        print("[1/3] 모델 목록 조회 실패 — Gemini API에 연결하지 못했습니다.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
