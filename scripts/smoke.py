#!/usr/bin/env python3
"""Verify the running local stack, including a real Chromium task and evidence."""

import json
import os
import sys
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


def main() -> None:
    base = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

    def request(path: str, *, body: dict | None = None, key: str | None = None):
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Idempotency-Key"] = key
        req = Request(
            base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
        )
        with urlopen(req, timeout=10) as response:
            return json.load(response)

    health = request("/health")
    if health.get("status") != "ok" or health.get("model_provider") != "mock":
        raise RuntimeError(f"예상한 mock API 상태가 아닙니다: {health}")
    key = f"smoke-{uuid.uuid4()}"
    payload = {"persona_name": "로컬 연결 검증", "task_id": "T02"}
    session = request("/sessions", body=payload, key=key)
    repeated = request("/sessions", body=payload, key=key)
    if session["id"] != repeated["id"]:
        raise RuntimeError("같은 요청 키로 중복 세션이 생성됐습니다.")

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        session = request(f"/sessions/{session['id']}")
        if session["status"] not in {"queued", "running"}:
            break
        time.sleep(0.5)
    if session["status"] != "succeeded":
        raise RuntimeError(
            f"과업 실행 실패: {session['status']} / {session.get('error')} "
            "(Redis, 워커, Chromium 설치 상태를 확인하세요.)"
        )
    steps = session["steps"]
    if len(steps) < 2 or not any(step["action"] == "click" for step in steps):
        raise RuntimeError("상품 정보 확인 동작이 기록되지 않았습니다.")

    screenshots = 0
    for step in steps:
        if step["status"] != "succeeded":
            raise RuntimeError(f"실패한 단계가 있습니다: {step}")
        if not step.get("screenshot_after"):
            raise RuntimeError("동작 이후 화면 기록이 없습니다.")
        if step["action"] == "click" and not step.get("screenshot_before"):
            raise RuntimeError("클릭 이전 화면 기록이 없습니다.")
        for phase in ("screenshot_before", "screenshot_after"):
            path = step.get(phase)
            if not path:
                continue
            url = urljoin(base + "/", path)
            if urlsplit(url).netloc != urlsplit(base).netloc:
                raise RuntimeError("화면 기록 URL이 로컬 API 바깥을 가리킵니다.")
            with urlopen(url, timeout=10) as response:
                if response.headers.get_content_type() != "image/png":
                    raise RuntimeError("화면 기록 응답이 PNG가 아닙니다.")
                if response.read(8) != b"\x89PNG\r\n\x1a\n":
                    raise RuntimeError("화면 기록 파일이 유효한 PNG가 아닙니다.")
            screenshots += 1
    listed = request("/sessions")
    if not any(item["id"] == session["id"] for item in listed):
        raise RuntimeError("완료된 세션이 목록에서 조회되지 않습니다.")
    print(f"연결 검증 통과: 세션 {session['id']}")
    print(f"API · 큐 · DB · Chromium · {len(steps)}개 단계 · PNG {screenshots}개 확인")
    print("동일 요청 재전송 시 세션 1개만 생성됨을 확인했습니다.")


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError, RuntimeError, KeyError, ValueError) as exc:
        print(f"연결 검증 실패: {exc}", file=sys.stderr)
        sys.exit(1)
