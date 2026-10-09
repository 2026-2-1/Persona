from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .security import normalize_origin
from .llm import load_env_file
from .runner import load_study
from .schemas import Persona, StudyConfig


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
RUN_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
OBS_ID = re.compile(r"^obs-[A-Za-z0-9_-]{1,100}$")
PROVIDERS = {"mock", "jev", "gemini", "live"}
PERSONA_CONTEXTS = [
    "검색 결과에서 여러 후보를 비교한 뒤 선택한다.",
    "안내 문구와 조건을 꼼꼼히 읽고 진행한다.",
    "필터와 정렬 기능이 보이면 활용한다.",
    "상세 정보에서 조건 충족 여부를 확인한다.",
    "다음에 할 수 있는 행동이 명확한 화면을 선호한다.",
    "정보를 찾기 어려우면 이전 화면으로 돌아가 다시 확인한다.",
    "페이지 제목과 메뉴를 먼저 읽어 화면 구성을 파악한다.",
    "선택한 조건이 유지되는지 중간에 다시 확인한다.",
    "불명확한 버튼은 주변 설명을 읽은 뒤 사용한다.",
    "후보의 차이점을 비교할 수 있는 정보를 찾는다.",
    "도움말이나 안내를 찾을 수 있으면 참고한다.",
    "최종 선택 전에 입력한 조건을 한 번 더 확인한다.",
]


def _json_file(path: Path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _jsonl_file(path: Path):
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append(row)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return rows


class Dashboard:
    def __init__(self, runs_dir="runs", personas_dir="runs/personas", study="configs/study.json"):
        self.runs_dir = Path(runs_dir).resolve()
        self.personas_dir = Path(personas_dir).resolve()
        self.study = Path(study).resolve()
        load_env_file(ROOT / ".env")
        self.job = None
        # start_job returns _job_state while holding this lock, so it must be reentrant.
        self.job_lock = threading.RLock()

    def _job_state(self):
        with self.job_lock:
            if not self.job:
                return None
            process = self.job["process"]
            if process.poll() is not None and self.job["status"] == "running":
                self.job["status"] = "completed" if process.returncode == 0 else "failed"
                self.job["finished_at"] = datetime.now(timezone.utc).isoformat()
                if process.returncode == 0:
                    self.job["message"] = (f"페르소나 {self.job['persona_count']}명 생성 완료" if self.job["kind"] == "generate"
                                           else "순차 테스트 실행을 마쳤습니다. 각 페르소나의 결과를 확인하세요.")
                else:
                    self.job["message"] = self._job_error(self.job["log_path"], process.returncode, self.job.get("study_id"))
            return {key: value for key, value in self.job.items() if key not in {"process", "log_path"}}

    def _job_error(self, path, returncode, study_id=None):
        try:
            lines = Path(path).read_text(encoding="utf-8")[-8000:].splitlines()
            message = next((line for line in reversed(lines) if line.startswith("error:")),
                           lines[-1] if lines else f"실행 실패 (종료 코드 {returncode})")
        except OSError:
            message = f"실행 실패 (종료 코드 {returncode})"
        if study_id:
            batch = _json_file(self.runs_dir / "batch_summary.json", {})
            if batch.get("study_id") == study_id:
                error = next((run["error"] for run in batch.get("runs", []) if run.get("error")), None)
                if error:
                    message = f"{batch['failed']}/{batch['requested']}명 실행 오류: {error}"
        for name in ("TYPESAFE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"):
            value = os.environ.get(name)
            if value:
                message = message.replace(value, "[redacted]")
        return message[:1000]

    def _run_folders(self):
        if not self.runs_dir.is_dir():
            return []
        return [path.parent for path in self.runs_dir.rglob("run.json")
                if path.resolve().is_relative_to(self.runs_dir)]

    def _run_folder(self, run_id):
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            return None
        return next((folder for folder in self._run_folders() if folder.name == run_id), None)

    def state(self):
        personas_file = self.personas_dir / "personas.jsonl"
        personas = []
        for raw in _jsonl_file(personas_file):
            if isinstance(raw, dict):
                personas.append(raw)
        runs = []
        if self.runs_dir.is_dir():
            for folder in self._run_folders():
                run = _json_file(folder / "run.json", {})
                persona = _json_file(folder / "persona.json", {})
                summary = _json_file(folder / "summary.json")
                steps = _jsonl_file(folder / "steps.jsonl")
                calls = _jsonl_file(folder / "llm_calls.jsonl")
                last_step = steps[-1] if steps else {}
                obs_id = last_step.get("next_observation_id") or last_step.get("observation_id")
                observations = list((folder / "observations").glob("obs-*.json"))
                if observations:
                    obs_id = max(observations, key=lambda item: item.stat().st_mtime_ns).stem
                observation = _json_file(folder / "observations" / f"{obs_id}.json", {}) if obs_id else {}
                runs.append({
                    "run_id": folder.name,
                    "persona_id": persona.get("persona_id"),
                    "persona": persona,
                    "study_id": run.get("study_id"),
                    "provider": run.get("provider"),
                    "model": run.get("model"),
                    "started_at": run.get("started_at"),
                    "active": summary is None,
                    "termination_reason": summary.get("termination_reason") if summary else None,
                    "verification": summary.get("verification") if summary else "running",
                    "steps": len(steps),
                    "action_attempts": summary.get("action_attempts", len(steps)) if summary else len(steps),
                    "llm_requests": summary.get("llm_request_count", len(calls)) if summary else len(calls),
                    "llm_tokens": summary.get("llm_tokens") if summary else sum((c.get("input_tokens") or 0) + (c.get("output_tokens") or 0) for c in calls),
                    "latest_observation_id": obs_id,
                    "latest_screenshot": f"/artifacts/{folder.name}/observations/{obs_id}.png" if obs_id and (folder / "observations" / f"{obs_id}.png").is_file() else None,
                    "latest_url": observation.get("url"),
                    "latest_title": observation.get("title"),
                    "latest_step": last_step,
                    "summary": summary,
                })
        runs.sort(key=lambda item: item.get("started_at") or "", reverse=True)
        for persona in personas:
            matches = [run for run in runs if run.get("persona") == persona]
            persona["run"] = matches[0] if matches else None
        job = self._job_state()
        if job and job["kind"] == "batch":
            job_runs = [run for run in runs if run["study_id"] == job["study_id"]]
            job["run_ids"] = [run["run_id"] for run in job_runs]
            job["finished_personas"] = sum(not run["active"] for run in job_runs)
        _, example, _ = load_study(self.study)
        persona_config = _json_file(ROOT / "configs" / "personas.json", {})
        return {
            "personas": personas,
            "generation": _json_file(self.personas_dir / "generation_manifest.json"),
            "runs": runs,
            "batch": _json_file(self.runs_dir / "batch_summary.json"),
            "job": job,
            "study": _json_file(self.study, {}),
            "persona_defaults": {"count": persona_config.get("count", 6), "background": example.background},
            "providers": {"jev": bool(os.environ.get("TYPESAFE_API_KEY") and os.environ.get("GEMINI_API_KEY")),
                          "gemini": bool(os.environ.get("GEMINI_API_KEY")), "live": bool(os.environ.get("OPENAI_API_KEY"))},
        }

    def run_detail(self, run_id):
        folder = self._run_folder(run_id)
        if folder is None:
            return None
        observations = {}
        obs_dir = folder / "observations"
        if obs_dir.is_dir():
            for path in obs_dir.glob("obs-*.json"):
                item = _json_file(path)
                if item:
                    item["screenshot_url"] = f"/artifacts/{run_id}/observations/{path.stem}.png" if (obs_dir / f"{path.stem}.png").is_file() else None
                    observations[path.stem] = item
        return {
            "run": _json_file(folder / "run.json", {}),
            "persona": _json_file(folder / "persona.json", {}),
            "config": _json_file(folder / "config.json", {}),
            "summary": _json_file(folder / "summary.json"),
            "steps": _jsonl_file(folder / "steps.jsonl"),
            "calls": _jsonl_file(folder / "llm_calls.jsonl"),
            "observations": observations,
        }

    def start_job(self, kind, provider="mock", start_url=None, task=None, persona_count=None, persona_background=None):
        if kind not in {"generate", "batch"}:
            raise ValueError("unknown job")
        if provider not in PROVIDERS:
            raise ValueError("unknown provider")
        config, example, _ = load_study(self.study)
        start_url = config.start_url if start_url is None else start_url
        task = config.task if task is None else task
        if not isinstance(start_url, str) or not start_url.strip() or len(start_url) > 2000:
            raise ValueError("테스트 URL을 입력하세요")
        if not isinstance(task, str) or not task.strip() or len(task) > 2000:
            raise ValueError("수행할 작업을 입력하세요 (최대 2000자)")
        start_url, task = start_url.strip(), task.strip()
        parsed = urlsplit(start_url)
        if parsed.username or parsed.password:
            raise ValueError("URL에 사용자명이나 비밀번호를 포함할 수 없습니다")
        try:
            origin = normalize_origin(start_url)
        except ValueError:
            raise ValueError("http:// 또는 https://로 시작하는 올바른 URL을 입력하세요") from None
        fixture = parsed.hostname in {"localhost", "127.0.0.1"} and parsed.path.endswith("shop.html")
        if kind == "batch":
            if provider == "mock" and not fixture:
                raise ValueError("Mock은 기본 데모 사이트 전용입니다. 외부 사이트에는 Jev 또는 Gemini를 선택하세요.")
            required = {"jev": ("TYPESAFE_API_KEY", "GEMINI_API_KEY"), "gemini": ("GEMINI_API_KEY",),
                        "live": ("OPENAI_API_KEY",)}.get(provider, ())
            if any(not os.environ.get(name) for name in required):
                raise ValueError(f"{provider} 실행에 필요한 API 키가 .env에 없습니다")
        with self.job_lock:
            if self.job and self.job["process"].poll() is None:
                raise RuntimeError("another dashboard job is already running")
            job_id = uuid.uuid4().hex[:10]
            job_dir = self.runs_dir / ".dashboard"
            job_dir.mkdir(parents=True, exist_ok=True)
            log_path = job_dir / f"{job_id}.log"
            if kind == "generate":
                generation_config = _json_file(ROOT / "configs" / "personas.json", {})
                count = generation_config.get("count", 6) if persona_count is None else persona_count
                if type(count) is not int or not 1 <= count <= 12:
                    raise ValueError("페르소나 수는 1~12명으로 입력하세요")
                if persona_background is not None:
                    if not isinstance(persona_background, str) or not persona_background.strip() or len(persona_background) > 2000:
                        raise ValueError("페르소나 설명을 입력하세요 (최대 2000자)")
                    background = persona_background.strip()
                    if background != example.background:
                        example.constraints = {}
                        example.preferences = ["작업에 명시된 조건을 확인", "화면 안내를 참고하여 선택"]
                    example.background = background
                example.intent = task
                example_path = job_dir / f"{job_id}-persona.json"
                example_path.write_text(example.model_dump_json(indent=2), encoding="utf-8")
                generation_config.update({"count": count, "seed": int(job_id, 16) % (2**31),
                                          "example_persona_file": str(example_path), "fixed_constraints": example.constraints,
                                          "contexts": PERSONA_CONTEXTS, "generation_id": job_id,
                                          "start_url": start_url, "task": task})
                generation_path = job_dir / f"{job_id}-personas.json"
                generation_path.write_text(json.dumps(generation_config, ensure_ascii=False), encoding="utf-8")
                command = [sys.executable, "-m", "uxagent", "personas", "--config", str(generation_path), "--output", str(self.personas_dir)]
                label = "페르소나 생성"
            else:
                personas_file = self.personas_dir / "personas.jsonl"
                if not personas_file.is_file():
                    raise FileNotFoundError("먼저 페르소나를 생성하세요")
                generated = [Persona.model_validate(raw) for raw in _jsonl_file(personas_file)]
                if not generated:
                    raise ValueError("생성된 페르소나가 없습니다. 먼저 생성하세요.")
                count = len(generated)
                example_path = job_dir / f"{job_id}-persona.json"
                example_path.write_text(generated[0].model_dump_json(indent=2), encoding="utf-8")
                study = config.model_dump()
                study.update({"study_id": f"dashboard-{job_id}", "start_url": start_url,
                              "allowed_origins": [origin], "task": task, "persona_file": str(example_path)})
                if not fixture:
                    study["evaluator_id"] = "unverified-external-site"
                    study["action_timeout_ms"] = max(study["action_timeout_ms"], 15000)
                StudyConfig.model_validate(study)
                study_path = job_dir / f"{job_id}-study.json"
                study_path.write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")
                command = [sys.executable, "-m", "uxagent", "batch", "--study", str(study_path), "--personas", str(personas_file), "--provider", provider, "--output", str(self.runs_dir)]
                label = "순차 사용자 테스트"
            log_handle = log_path.open("ab")
            try:
                process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log_handle,
                                           stderr=subprocess.STDOUT, start_new_session=True)
            finally:
                log_handle.close()
            self.job = {"job_id": job_id, "kind": kind, "label": label, "provider": "mock" if kind == "generate" else provider,
                        "status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
                        "log_path": str(log_path), "process": process, "persona_count": count,
                        "study_id": f"dashboard-{job_id}" if kind == "batch" else None,
                        "message": "페르소나를 생성하고 있습니다." if kind == "generate" else "첫 페르소나의 브라우저를 시작하고 있습니다."}
            return self._job_state()


def make_handler(dashboard: Dashboard):
    class Handler(BaseHTTPRequestHandler):
        server_version = "UXAgentDashboard/1.0"

        def _send(self, status, body, content_type="application/json; charset=utf-8"):
            payload = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            try:
                self._get()
            except (OSError, ValueError, TypeError, KeyError) as exc:
                self._send(500, {"error": f"상태를 읽지 못했습니다 ({type(exc).__name__}). 서버 설정을 확인하세요."})

        def _get(self):
            path = urlsplit(self.path).path
            if path == "/api/state":
                return self._send(200, dashboard.state())
            if path.startswith("/api/run/"):
                detail = dashboard.run_detail(unquote(path.removeprefix("/api/run/")))
                return self._send(200, detail) if detail else self._send(404, {"error": "run_not_found"})
            if path.startswith("/artifacts/"):
                parts = [unquote(part) for part in path.split("/") if part]
                if len(parts) != 4 or not RUN_ID.fullmatch(parts[1]) or parts[2] != "observations" or not parts[3].endswith(".png") or not OBS_ID.fullmatch(parts[3][:-4]):
                    return self._send(404, {"error": "artifact_not_found"})
                folder = dashboard._run_folder(parts[1])
                if folder is None:
                    return self._send(404, {"error": "artifact_not_found"})
                target = (folder / parts[2] / parts[3]).resolve()
                if not target.is_relative_to(dashboard.runs_dir) or not target.is_file():
                    return self._send(404, {"error": "artifact_not_found"})
                return self._send(200, target.read_bytes(), "image/png")
            if path in {"/", "/index.html"}:
                return self._send(200, (PACKAGE / "dashboard" / "index.html").read_bytes(), "text/html; charset=utf-8")
            if path == "/dashboard.js":
                return self._send(200, (PACKAGE / "dashboard" / "app.js").read_bytes(), "text/javascript; charset=utf-8")
            return self._send(404, {"error": "not_found"})

        def do_POST(self):
            if urlsplit(self.path).path != "/api/jobs":
                return self._send(404, {"error": "not_found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 16384:
                    return self._send(413, {"error": "request_too_large"})
                payload = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("요청 형식이 올바르지 않습니다")
                job = dashboard.start_job(payload.get("kind"), payload.get("provider", "mock"), payload.get("start_url"), payload.get("task"),
                                          payload.get("persona_count"), payload.get("persona_background"))
                return self._send(202, job)
            except (ValueError, OSError, RuntimeError) as exc:
                return self._send(409 if isinstance(exc, RuntimeError) else 400, {"error": str(exc)})

        def log_message(self, format, *args):
            # Keep HTTP access logs free of query strings and request data.
            return

    return Handler


def serve_dashboard(port=8765, runs_dir="runs", personas_dir="runs/personas", study="configs/study.json"):
    dashboard = Dashboard(runs_dir, personas_dir, study)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(dashboard))
    print(f"UXAgent dashboard: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
