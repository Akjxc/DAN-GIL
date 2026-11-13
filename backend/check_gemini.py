"""Run locally in the same PowerShell session that holds the API key.

python -m backend.check_gemini
Only lists model IDs and prints result/status/timing. Never prints credentials,
provider exception bodies, conversation history, or executes routing functions.
"""

import argparse
import os
import time

import httpx
from google import genai
from google.genai import errors, types

from backend.agent import generation_config


def run_checks(client, model: str) -> int:
    print(f"Model: {model}", flush=True)
    try:
        models = list(client.models.list())
    except errors.APIError as exc:
        print(f"MODEL_LIST FAILED: HTTP {exc.code}", flush=True)
        return 1
    available = {m.name.removeprefix("models/"): m for m in models if m.name}
    selected = model.removeprefix("models/")
    if selected not in available:
        print("MODEL_NOT_LISTED: configured model was not returned by this API key.")
        print("Listed Flash models (listing does not prove free quota):")
        for name, item in sorted(available.items()):
            if "flash" in name and "generateContent" in (item.supported_actions or []):
                print(f"  {name}")
        return 1
    print("MODEL_LIST OK", flush=True)
    failed = False
    for label, config in [
        ("PLAIN", types.GenerateContentConfig()),
        ("WITH_TOOLS", generation_config()),
    ]:
        started = time.monotonic()
        print(f"{label}: requesting...", flush=True)
        try:
            response = client.models.generate_content(
                model=model, contents="Hello. Reply with a short greeting.", config=config
            )
            candidate = (response.candidates or [None])[0]
            parts = candidate.content.parts if candidate and candidate.content else []
            text = any(p.text and not p.thought for p in (parts or []))
            calls = sum(p.function_call is not None for p in (parts or []))
            if text or calls:
                outcome = f"OK text={bool(text)} function_calls={calls}"
            else:
                outcome = "EMPTY_RESPONSE"
                failed = True
        except errors.APIError as exc:
            outcome = f"FAILED HTTP {exc.code}"
            failed = True
        except httpx.TimeoutException:
            outcome = "CLIENT_TIMEOUT"
            failed = True
        except httpx.TransportError:
            outcome = "CONNECTION_ERROR"
            failed = True
        print(f"{label}: {outcome} elapsed={time.monotonic() - started:.1f}s", flush=True)
    return int(failed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=60, choices=range(1, 121), metavar="SECONDS")
    args = parser.parse_args()
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "").strip()
    if not key or not model:
        print("Set GEMINI_API_KEY and GEMINI_MODEL in this terminal first.")
        return 1
    print(f"SDK: {genai.__version__}; per-request timeout: {args.timeout}s; retries: disabled", flush=True)
    try:
        with genai.Client(api_key=key, http_options=types.HttpOptions(
            timeout=args.timeout * 1000,
            retry_options=types.HttpRetryOptions(attempts=1),
        )) as client:
            return run_checks(client, model)
    except httpx.TimeoutException:
        print("MODEL_LIST CLIENT_TIMEOUT")
        return 1
    except httpx.TransportError:
        print("MODEL_LIST CONNECTION_ERROR")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
