from __future__ import annotations

import asyncio, hashlib, json, os, threading, time, urllib.request, urllib.error
import ssl
from pathlib import Path


GEMINI_MODEL = "gemini-2.5-flash-lite"
CLAUDE_MODEL = "claude-sonnet-4-6"
GEMINI_INPUT_USD_PER_MILLION = 0.10
GEMINI_OUTPUT_USD_PER_MILLION = 0.40
JEV_INPUT_USD_PER_MILLION = 0.042


def _transport_error(exc):
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, ssl.SSLCertVerificationError):
        return "provider_tls_error:certificate_verification_failed"
    return f"provider_transient:{type(reason).__name__}"


def load_env_file(path: str | Path = ".env"):
    """Load simple KEY=VALUE entries without overriding the process environment."""
    configure_ssl_certificates()
    path = Path(path)
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip("\"'")
        if name and name not in os.environ:
            os.environ[name] = value


def configure_ssl_certificates():
    """Use an available OS CA bundle if this Python install has no default CA file."""
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return
    paths = ssl.get_default_verify_paths()
    if paths.cafile and Path(paths.cafile).is_file():
        return
    candidates = [paths.openssl_cafile, "/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"]
    ca_file = next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)
    if ca_file:
        os.environ["SSL_CERT_FILE"] = ca_file


def estimate_cost_usd(provider: str, input_tokens: int | None, output_tokens: int | None):
    if input_tokens is None or output_tokens is None:
        return None
    if provider == "gemini":
        return round(input_tokens * GEMINI_INPUT_USD_PER_MILLION / 1_000_000 +
                     output_tokens * GEMINI_OUTPUT_USD_PER_MILLION / 1_000_000, 10)
    if provider == "typesafe":
        return round(input_tokens * JEV_INPUT_USD_PER_MILLION / 1_000_000, 10)
    return None


class JevProvider:
    model = "jev-latest"

    async def choose(self, state, candidates):
        return await asyncio.to_thread(self._choose, state, candidates)

    async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
        return await GeminiProvider().complete(messages, model or GEMINI_MODEL, temperature, max_tokens)

    def _choose(self, state, candidates):
        key = os.environ.get("TYPESAFE_API_KEY")
        if not key:
            raise RuntimeError("TYPESAFE_API_KEY is required")
        body = json.dumps({"model": self.model, "state": state, "questions": {
            "next_action": {"type": "choice", "instructions": "Which single browser action should be taken next? Choose the action that best advances the user's task using only this observed page state.",
                            "criteria": {c["id"]: c["description"] for c in candidates}}
        }}, ensure_ascii=False).encode()
        req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"provider_http_{exc.code}") from None
        except urllib.error.URLError as exc:
            raise RuntimeError(_transport_error(exc)) from None
        except (TimeoutError, ConnectionError) as exc:
            raise RuntimeError(_transport_error(exc)) from None
        answer = data.get("answers", {}).get("next_action", {})
        return answer.get("choice"), answer.get("confidence"), answer.get("probabilities", {}), {
            "model": data.get("model", self.model),
            "input_tokens": data.get("usage", {}).get("input_tokens"),
            "output_tokens": data.get("usage", {}).get("output_tokens"),
        }


class GeminiProvider:
    model = GEMINI_MODEL

    async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
        return await asyncio.to_thread(self._complete, messages, model or self.model, temperature, max_tokens)

    def _complete(self, messages, model, temperature, max_tokens):
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is required")
        contents = []
        system = []
        for message in messages:
            if message["role"] == "system": system.append(message["content"])
            else: contents.append({"role": "user" if message["role"] == "user" else "model", "parts": [{"text": message["content"]}]})
        body_data = {"contents": contents, "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json"}}
        if system:
            body_data["systemInstruction"] = {"parts": [{"text": "\n".join(system)}]}
        body = json.dumps(body_data, ensure_ascii=False).encode()
        req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=body, headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as response: data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"provider_http_{exc.code}") from None
        except urllib.error.URLError as exc:
            raise RuntimeError(_transport_error(exc)) from None
        except (TimeoutError, ConnectionError) as exc:
            raise RuntimeError(_transport_error(exc)) from None
        usage = data.get("usageMetadata", {})
        content = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        return content, {"model": model, "input_tokens": usage.get("promptTokenCount"), "output_tokens": usage.get("candidatesTokenCount")}


class ClaudeProvider:
    model = CLAUDE_MODEL

    async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
        return await asyncio.to_thread(self._complete, messages, model or self.model, temperature, max_tokens)

    def _complete(self, messages, model, temperature, max_tokens):
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for --provider claude")
        system = [message["content"] for message in messages if message["role"] == "system"]
        body = {"model": model, "messages": [message for message in messages if message["role"] != "system"],
                "temperature": temperature, "max_tokens": max_tokens}
        if system:
            body["system"] = "\n".join(system)
        request = urllib.request.Request("https://api.anthropic.com/v1/messages",
            data=json.dumps(body, ensure_ascii=False).encode(),
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 529:
                raise RuntimeError("provider_transient:provider_http_529") from None
            raise RuntimeError(f"provider_http_{exc.code}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise RuntimeError(_transport_error(exc)) from None
        content = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        usage = data.get("usage", {})
        return content, {"model": data.get("model", model), "input_tokens": usage.get("input_tokens"),
                         "output_tokens": usage.get("output_tokens")}


class BudgetExceeded(RuntimeError): pass


class BudgetManager:
    def __init__(self, max_requests: int, max_tokens: int):
        self.max_requests, self.max_tokens = max_requests, max_tokens
        self.requests = self.tokens = self.reserved_tokens = 0
        self.lock = threading.Lock()

    def reserve(self, estimated_tokens: int):
        with self.lock:
            if self.requests >= self.max_requests or self.tokens + self.reserved_tokens + estimated_tokens > self.max_tokens:
                raise BudgetExceeded("LLM request or token budget exhausted")
            self.requests += 1
            self.reserved_tokens += estimated_tokens

    def settle(self, reservation: int, actual: int | None):
        with self.lock:
            self.reserved_tokens = max(0, self.reserved_tokens - reservation)
            # If a provider omits usage, retain the conservative reservation.
            self.tokens += reservation if actual is None else max(0, actual)

    def snapshot(self):
        return {"requests": self.requests, "tokens": self.tokens, "reserved_tokens": self.reserved_tokens,
                "max_requests": self.max_requests, "max_tokens": self.max_tokens}


class MockProvider:
    model = "mock-v1"
    async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
        payload = json.loads(messages[-1]["content"])
        if "Summarize up to three brief insights" in messages[0]["content"]:
            ids=[m["memory_id"] for m in payload.get("memories",[]) if m.get("content_status")=="observed"][-2:]
            insights=[]
            if ids:insights=[{"summary":"최근 관찰과 행동 기록을 바탕으로 다음 화면에서 조건 적용 여부를 확인합니다.","source_memory_ids":ids}]
            return json.dumps({"insights":insights,"next_focus":"현재 화면과 사용자 조건을 다시 확인합니다."},ensure_ascii=False),{"model":"mock-v1","input_tokens":0,"output_tokens":0}
        obs = payload["observation"]
        memories = payload.get("memories", [])
        action_types = [m.get("action_type") for m in memories]
        inputs = obs.get("input_elements", [])
        clicks = obs.get("clickable_elements", [])
        selects = obs.get("select_elements", [])
        def target(items, name): return next((x for x in items if name in x["name"]), None)
        action = None
        finish = None
        if payload.get("evaluator_success"):
            finish = {"claim":"completed", "summary":"조건에 맞는 상품 상세 화면을 확인했습니다."}
        elif "type" not in action_types:
            x = target(inputs, "상품 검색")
            action = {"type":"type", "observation_id":obs["observation_id"], "tab_id":obs["tab_id"], "target_id":x["id"], "text":"가방"} if x else None
        elif "click-search" not in action_types:
            x=target(clicks,"검색")
            action={"type":"click","observation_id":obs["observation_id"],"tab_id":obs["tab_id"],"target_id":x["id"]} if x else None
        elif "select-color" not in action_types:
            x=target(selects,"색상")
            action={"type":"select","observation_id":obs["observation_id"],"tab_id":obs["tab_id"],"target_id":x["id"],"option_value":"검정"} if x else None
        elif "select-price" not in action_types:
            x=target(selects,"최대 가격")
            action={"type":"select","observation_id":obs["observation_id"],"tab_id":obs["tab_id"],"target_id":x["id"],"option_value":"30000"} if x else None
        elif "apply-filter" not in action_types:
            x=target(clicks,"필터 적용")
            action={"type":"click","observation_id":obs["observation_id"],"tab_id":obs["tab_id"],"target_id":x["id"]} if x else None
        else:
            x=target(clicks,"상세 보기")
            action={"type":"click","observation_id":obs["observation_id"],"tab_id":obs["tab_id"],"target_id":x["id"]} if x else None
        if action is None and finish is None:
            finish={"claim":"give_up","summary":"현재 화면에서 다음 행동 대상을 찾을 수 없습니다."}
        return json.dumps({"perception":"현재 페이지의 검색과 상품 정보를 확인했습니다.","plan":"페르소나의 가격과 색상 조건을 적용하고 상세를 확인합니다.","rationale_summary":"조건에 맞는 상품을 단계적으로 확인합니다.","action":action,"finish":finish}, ensure_ascii=False), {"model":"mock-v1","input_tokens":0,"output_tokens":0}

    async def embed(self, texts, model):
        vectors=[]
        for text in texts:
            vector=[0.0]*64
            for token in text.lower().split():
                digest=hashlib.sha256(token.encode()).digest();index=int.from_bytes(digest[:2],"big")%64
                vector[index]+=1.0 if digest[2]&1 else -1.0
            vectors.append(vector)
        return vectors,{"model":model,"input_tokens":0,"output_tokens":0}


class OpenAIProvider:
    model = None
    async def complete(self, messages, model, temperature=0.2, max_tokens=1200):
        return await asyncio.to_thread(self._complete, messages, model, temperature, max_tokens)

    def _complete(self, messages, model, temperature, max_tokens):
        key = os.environ.get("OPENAI_API_KEY")
        if not key: raise RuntimeError("OPENAI_API_KEY is required for --provider live")
        body = json.dumps({"model":model,"messages":messages,"temperature":temperature,"max_tokens":max_tokens,"response_format":{"type":"json_object"}}).encode()
        req=urllib.request.Request("https://api.openai.com/v1/chat/completions",data=body,headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as response: data=json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8","replace")[:400]
            raise RuntimeError(f"provider_http_{exc.code}: {detail}") from exc
        except (urllib.error.URLError,TimeoutError,ConnectionError) as exc:
            raise RuntimeError(f"provider_transient: {str(exc)[:300]}") from exc
        usage=data.get("usage",{})
        return data["choices"][0]["message"]["content"], {"model":data.get("model",model),"input_tokens":usage.get("prompt_tokens"),"output_tokens":usage.get("completion_tokens")}

    async def embed(self, texts, model):
        return await asyncio.to_thread(self._embed, texts, model)

    def _embed(self, texts, model):
        key=os.environ.get("OPENAI_API_KEY")
        if not key:raise RuntimeError("OPENAI_API_KEY is required for embeddings")
        body=json.dumps({"model":model,"input":texts,"encoding_format":"float"}).encode()
        req=urllib.request.Request("https://api.openai.com/v1/embeddings",data=body,headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req,timeout=60) as response:data=json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8","replace")[:400]
            raise RuntimeError(f"provider_http_{exc.code}: {detail}") from exc
        except (urllib.error.URLError,TimeoutError,ConnectionError) as exc:
            raise RuntimeError(f"provider_transient: {str(exc)[:300]}") from exc
        ordered=sorted(data["data"],key=lambda item:item["index"])
        usage=data.get("usage",{})
        return [item["embedding"] for item in ordered],{"model":data.get("model",model),"input_tokens":usage.get("prompt_tokens"),"output_tokens":0}
