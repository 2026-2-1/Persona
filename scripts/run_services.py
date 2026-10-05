"""Own and clean up only the development processes started by this invocation."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / ".cache" / "logs"
stopping = False


def request_stop(_signum: int, _frame: object) -> None:
    global stopping
    stopping = True


def assert_port_available(port: int) -> None:
    with socket.socket() as connection:
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            connection.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(
                f"{port} 포트를 다른 프로그램이 사용합니다. 기존 실행을 종료하고 다시 시작하세요."
            ) from error


def wait_for_api(process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline and not stopping:
        if process.poll() is not None:
            raise RuntimeError(f"API가 종료됐습니다. {LOGS / 'api.log'}를 확인하세요.")
        try:
            with urlopen("http://127.0.0.1:8000/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.3)
    if not stopping:
        raise RuntimeError(f"API 응답을 기다리다 실패했습니다. {LOGS / 'api.log'}를 확인하세요.")


def shutdown(processes: list[tuple[str, subprocess.Popen[bytes]]]) -> None:
    # 각 실행에 새 프로세스 그룹을 만들었으므로 npm/uv의 자식도 함께 종료합니다.
    for _, process in reversed(processes):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 8
    while any(process.poll() is None for _, process in processes):
        if time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    for _, process in processes:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def main() -> int:
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    processes: list[tuple[str, subprocess.Popen[bytes]]] = []
    log_files = []
    exit_code = 0
    try:
        assert_port_available(8000)
        assert_port_available(3000)
        LOGS.mkdir(parents=True, exist_ok=True)
        services = [
            (
                "api",
                [
                    "uv", "run", "--frozen", "uvicorn", "persona.api:app",
                    "--host", "127.0.0.1", "--port", "8000", "--reload",
                ],
                ROOT / "backend",
            ),
            (
                "worker",
                [
                    "uv", "run", "--frozen", "celery", "-A", "persona.worker:celery_app",
                    "worker", "--loglevel=info", "--pool=solo", "--concurrency=1",
                ],
                ROOT / "backend",
            ),
            (
                "web",
                ["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3000"],
                ROOT / "apps" / "web",
            ),
        ]
        for name, command, directory in services:
            if stopping:
                break
            log_file = (LOGS / f"{name}.log").open("w", encoding="utf-8")
            log_files.append(log_file)
            process = subprocess.Popen(
                command,
                cwd=directory,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            processes.append((name, process))
            if name == "api":
                wait_for_api(process)
        if not stopping:
            print("\n개발 화면: http://127.0.0.1:3000", flush=True)
            print("API 문서:  http://127.0.0.1:8000/docs", flush=True)
            print(f"실행 로그: {LOGS}", flush=True)
            print(
                "종료하려면 Ctrl+C를 누르세요. PostgreSQL/Redis 데이터는 유지됩니다.\n",
                flush=True,
            )
        while not stopping:
            for name, process in processes:
                result = process.poll()
                if result is not None:
                    raise RuntimeError(
                        f"{name} 프로세스가 종료됐습니다(코드 {result}). "
                        f"{LOGS / f'{name}.log'}를 확인하세요."
                    )
            time.sleep(0.5)
    except (RuntimeError, OSError) as error:
        print(f"오류: {error}", file=sys.stderr, flush=True)
        exit_code = 1
    finally:
        shutdown(processes)
        for log_file in log_files:
            log_file.close()
        print("이 실행에서 시작한 개발 프로세스를 종료했습니다.", flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
