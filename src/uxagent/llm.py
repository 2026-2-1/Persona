from __future__ import annotations

import asyncio, hashlib, json, os, threading, time, urllib.request, urllib.error
import ssl
import base64
from pathlib import Path
from collections import deque
from urllib.parse import urlsplit


GEMINI_MODEL = "gemini-2.5-flash-lite"
CLAUDE_MODEL = "claude-sonnet-4-6"
GEMINI_INPUT_USD_PER_MILLION = 0.10
GEMINI_OUTPUT_USD_PER_MILLION = 0.40
JEV_INPUT_USD_PER_MILLION = 0.042
# OpenAI standard (non-batch) prices for the live catalog models: (input, output) USD per 1M tokens.
OPENAI_USD_PER_MILLION = {"gpt-4o-mini": (0.15, 0.60), "gpt-4.1-mini": (0.40, 1.60),
                         "gpt-4o-mini-2024-07-18": (0.15, 0.60),
                         "gpt-4.1-mini-2025-04-14": (0.40, 1.60)}


def provider_for_model(model: str | None, fallback: str = "unknown") -> str:
    model = str(model or "")
    if model.startswith("gemini-"):
        return "gemini"
    if model.startswith("jev-"):
        return "typesafe"
    if model.startswith("claude-"):
        return "claude"
    if model.startswith("gpt-"):
        return "openai"
    if model == "mock-v1":
        return "mock"
    if model == "persona-qwen":
        return "gpu"
    return fallback


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


def estimate_cost_usd(provider: str, input_tokens: int | None, output_tokens: int | None, model: str | None = None):
    if input_tokens is None or output_tokens is None:
        return None
    if provider == "gemini":
        if model is not None and model != GEMINI_MODEL:
            return None
        return round(input_tokens * GEMINI_INPUT_USD_PER_MILLION / 1_000_000 +
                     output_tokens * GEMINI_OUTPUT_USD_PER_MILLION / 1_000_000, 10)
    if provider == "typesafe":
        if model is not None and model != "jev-latest":
            return None
        return round(input_tokens * JEV_INPUT_USD_PER_MILLION / 1_000_000, 10)
    if provider in ("openai", "other") and model in OPENAI_USD_PER_MILLION:
        input_price, output_price = OPENAI_USD_PER_MILLION[model]
        return round(input_tokens * input_price / 1_000_000 + output_tokens * output_price / 1_000_000, 10)
    return None


class JevProvider:
    model = "jev-latest"

    async def choose(self, state, candidates):
        return await asyncio.to_thread(self._choose, state, candidates)

    async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
        content, usage = await GeminiProvider().complete(messages, model or GEMINI_MODEL, temperature, max_tokens)
        return content, {**usage, "provider": "gemini"}

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


class BudgetExceeded(RuntimeError):
    def __init__(self, reason_code):
        self.reason_code = reason_code
        super().__init__(f"LLM budget exhausted: {reason_code}")


class BudgetManager:
    def __init__(self, max_requests: int | None, max_tokens: int | None):
        self.max_requests, self.max_tokens = max_requests, max_tokens
        self.requests = self.tokens = self.reserved_tokens = 0
        self.last_exceeded_reason = None
        self.lock = threading.Lock()

    def reserve(self, estimated_tokens: int):
        with self.lock:
            if self.max_requests is not None and self.requests >= self.max_requests:
                self.last_exceeded_reason = "request_limit"
                raise BudgetExceeded("request_limit")
            if self.max_tokens is not None and self.tokens + self.reserved_tokens + estimated_tokens > self.max_tokens:
                self.last_exceeded_reason = "token_limit"
                raise BudgetExceeded("token_limit")
            self.requests += 1
            self.reserved_tokens += estimated_tokens

    def settle(self, reservation: int, actual: int | None):
        with self.lock:
            self.reserved_tokens = max(0, self.reserved_tokens - reservation)
            # If a provider omits usage, retain the conservative reservation.
            self.tokens += reservation if actual is None else max(0, actual)

    def snapshot(self):
        return {"requests": self.requests, "tokens": self.tokens, "reserved_tokens": self.reserved_tokens,
                "max_requests": self.max_requests, "max_tokens": self.max_tokens,
                "last_exceeded_reason": self.last_exceeded_reason}


class MockProvider:
    model = "mock-v1"

    def set_observation(self, observation):
        """Fixture-only adapter; observation metadata is not added to real U prompts."""
        self.fixture_observation = observation

    async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
        system = messages[0]["content"]
        if system.startswith("Answer the supplied questionnaire "):
            questionnaire_text, trace_text, *facts = messages[-1]["content"].split("\n", 2)
            questionnaire = json.loads(questionnaire_text)
            memories = json.loads(trace_text)
            errors = json.loads(facts[0])['execution_trace']['error_count'] if facts else None
            answers = []
            for question in questionnaire["questions"]:
                if question["type"] == "multiple_choice":
                    value = next((option for option in question["options"]
                                  if option.lower() in {"n/a", "기억나지 않는다", "해당 없음"}),
                                 question["options"][0])
                else:
                    value = "N/A" if not memories else "기록된 기억을 참고했습니다."
                answers.append({"question_id": question["id"], "value": value,
                                "reason": "로컬 fixture 응답이며 실제 GPU 설문 호출이 아닙니다."})
            return json.dumps({"questionnaire_id": questionnaire["questionnaire_id"],
                               "answers": answers, "meta": {"confidence_overall": 0.0,
                                                            'execution_error_count': errors}},
                              ensure_ascii=False), {
                "provider": "mock", "model": self.model, "input_tokens": 0, "output_tokens": 0,
            }
        payload = json.loads(messages[-1]["content"])
        if system.startswith('FAST_STAGE:search_query'):
            return json.dumps({'use_search': True, 'query': '가방', 'reason': '합성 쇼핑 fixture의 검색어입니다.'}, ensure_ascii=False), {
                'model': self.model, 'provider': 'mock', 'input_tokens': 0, 'output_tokens': 0}
        if system.startswith('FAST_STAGE:popup_decision'):
            popup = payload['popup']
            close = next((c for c in popup['controls'] if c['name'].lower() in {'close', '닫기', '팝업 닫기', '창 닫기'}), None)
            result = {'choice': 'interact' if close else 'stop' if popup['modal'] else 'ignore',
                      'reason': '합성 fixture 팝업 판단입니다.',
                      'action': {'action': 'click', 'target': close['id'], 'description': '관찰한 닫기를 선택합니다.'} if close else None}
            return json.dumps(result, ensure_ascii=False), {
                'model': self.model, 'provider': 'mock', 'input_tokens': 0, 'output_tokens': 0}
        if system.startswith("SLOW_STAGE:"):
            # Synthetic transport latency for the fixture provider only. The real
            # scheduler has no delay/rate gate; empty later outputs are valid U JSON.
            await asyncio.sleep(0.001)
            stage = system.split(":", 1)[1].splitlines()[0]
            if stage == "reflection":
                result = {"insights": [] if getattr(self, "fixture_reflected", False) else ["최근 기억을 참고해 화면 조건을 확인합니다."]}
                self.fixture_reflected = True
            elif stage == "wonder":
                result = {"thoughts": [] if getattr(self, "fixture_wondered", False) else ["현재 기억과 과업을 떠올립니다."]}
                self.fixture_wondered = True
            else:
                result = {"score": 5, "rationale": "Mock importance score."}
            return json.dumps(result, ensure_ascii=False), {"model":"mock-v1","input_tokens":0,"output_tokens":0}
        if "FAST_STAGE:perception" in system and isinstance(payload, str):
            return json.dumps({"observations":[payload]},ensure_ascii=False),{"model":"mock-v1","input_tokens":0,"output_tokens":0}
        if "FAST_STAGE:feedback" in system:
            return json.dumps({"thoughts":["직전 제안과 새 화면을 확인했습니다."]},ensure_ascii=False),{"model":"mock-v1","input_tokens":0,"output_tokens":0}
        if "FAST_STAGE:plan" in system and "old_plan" in payload:
            return json.dumps({"plan":"조건에 맞는 상품의 검색·필터·상세를 확인합니다.",
                "rationale":"현재 관찰과 제안 행동을 바탕으로 진행합니다.","next_step":"다음 검색·필터·상세 행동"},ensure_ascii=False),{"model":"mock-v1","input_tokens":0,"output_tokens":0}
        if "FAST_STAGE:decision" in system and "environment" in payload:
            history = getattr(self, "fixture_history", [])
            legacy_payload = {"observation":self.fixture_observation.model_dump(),
                              "recent_actions":[{"action_type":stage} for stage in history]}
            response, usage = self._fixture_decision(legacy_payload)
            selected = json.loads(response)
            action = selected["action"]
            if action is None:
                raw={"action":"terminate","description":selected["finish"]["summary"]}
            else:
                raw={"action":action["type"],"description":f"{action['type']} {action.get('target_id','')}"}
                for source,target in (("target_id","target"),("text","text"),("option_value","value")):
                    if source in action:raw[target]=action[source]
                stages=["type","click-search","select-color","select-price","apply-filter","detail"]
                self.fixture_history=[*history,stages[min(len(history),len(stages)-1)]]
            return json.dumps({"actions":[raw]},ensure_ascii=False),usage
        if "Rate the importance of one memory" in messages[0]["content"]:
            return json.dumps({"score":5,"reason":"Mock importance score for a saved memory."}),{"model":"mock-v1","input_tokens":0,"output_tokens":0}
        if "WONDER_PERSONA_ONLY" in system:
            return json.dumps({"thought":"저녁에는 따뜻한 차를 마셔 볼까?"},ensure_ascii=False),{"model":"mock-v1","input_tokens":0,"output_tokens":0}
        if "Summarize up to three brief insights" in messages[0]["content"]:
            ids=[m["memory_id"] for m in payload.get("memories",[]) if m.get("content_status")=="observed" or m.get("kind")=="observation"][-2:]
            insights=[]
            if ids:insights=[{"summary":"최근 관찰과 행동 기록을 바탕으로 다음 화면에서 조건 적용 여부를 확인합니다.","source_memory_ids":ids}]
            return json.dumps({"insights":insights,"next_focus":"현재 화면과 사용자 조건을 다시 확인합니다."},ensure_ascii=False),{"model":"mock-v1","input_tokens":0,"output_tokens":0}
        if "Review whether the supplied plan" in messages[0]["content"]:
            return json.dumps({"review":"현재 계획은 과업 의도와 일치합니다.","suggested_revisions":[]},ensure_ascii=False),{"model":"mock-v1","input_tokens":0,"output_tokens":0}
        if "FAST_STAGE:perception" in system:
            obs = payload["observation"]
            visible = [e.get("name") for e in obs.get("clickable_elements", []) + obs.get("input_elements", []) + obs.get("select_elements", [])]
            text = "현재 화면에서 " + (", ".join(x for x in visible if x) or "과업 진행 요소") + "을 확인했습니다."
            return json.dumps({"perception":text},ensure_ascii=False),{"model":"mock-v1","input_tokens":0,"output_tokens":0}
        if "FAST_STAGE:plan" in system:
            return json.dumps({"plan":"과업과 페르소나 조건에 맞는 화면 요소를 사용하고 결과를 확인합니다."},ensure_ascii=False),{"model":"mock-v1","input_tokens":0,"output_tokens":0}
        if "FAST_STAGE:decision" in system:
            return self._fixture_decision(payload)
        obs = payload["observation"]
        memories = payload.get("memories", [])
        action_types = [m.get("action_type") for m in [*memories, *payload.get("recent_actions", [])]]
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

    def _fixture_decision(self, payload):
        obs = payload["observation"]
        memories = payload.get("memories", [])
        action_types = [m.get("action_type") for m in [*memories, *payload.get("recent_actions", [])]]
        inputs, clicks, selects = obs.get("input_elements", []), obs.get("clickable_elements", []), obs.get("select_elements", [])
        def target(items, name): return next((x for x in items if name in x["name"]), None)
        action = None
        if "type" not in action_types:
            x=target(inputs,"상품 검색")
            action={"type":"type","observation_id":obs["observation_id"],"tab_id":obs["tab_id"],"target_id":x["id"],"text":"가방"} if x else None
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
        finish = {"claim":"give_up","summary":"현재 화면에서 다음 행동 대상을 찾을 수 없습니다."} if action is None else None
        return json.dumps({"rationale_summary":"현재 관찰과 계획을 바탕으로 다음 행동을 선택합니다.","action":action,"finish":finish},ensure_ascii=False),{"model":"mock-v1","input_tokens":0,"output_tokens":0}

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


class ProviderConnectionError(RuntimeError):
    """The model endpoint is unavailable; no model output was received."""


class LocalQwenProvider:
    """OpenAI-compatible Qwen API reached through a local SSH tunnel."""

    model = "persona-qwen"

    def __init__(self):
        from .prompt_guard import PromptGuard
        from .token_counter import QwenTokenCounter
        counter_url = os.environ.get('PERSONA_QWEN_TOKENIZER_URL')
        self.prompt_guard = PromptGuard(QwenTokenCounter(counter_url) if counter_url else None)
        self._loop = None
        self._worker = None
        self._fast_pending = deque()
        self._slow_pending = deque()

    async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
        summaries = []
        prepared = await self.prepare_messages(messages, model or self.model, max_tokens,
                                               call_log=summaries.append)
        content, usage = await self._enqueue(prepared, model or self.model, temperature, max_tokens)
        if summaries:
            for key in ('input_tokens', 'output_tokens'):
                values = [usage.get(key)] + [row.get(key) for row in summaries]
                usage[key] = sum(values) if all(value is not None for value in values) else None
        return content, {**usage, 'prompt_guard': self.prompt_guard.metadata(prepared, max_tokens),
                         **({'prompt_summary_requests': len(summaries)} if summaries else {})}

    async def prepare_messages(self, messages, model, max_tokens, *, budget=None,
                               call_log=None, module='provider', stage='completion'):
        return await self.prompt_guard.prepare(messages, model, max_tokens,
            send=self._enqueue, budget=budget if budget is not None else BudgetManager(None, None),
            call_log=call_log, module=module, stage=stage)

    async def complete_image(self, messages, image_path, temperature=0.2, max_tokens=512):
        if not os.environ.get('PERSONA_QWEN_VISION_API_URL') or not os.environ.get('PERSONA_QWEN_VISION_MODEL'):
            raise RuntimeError('popup_vision_unavailable: configure a local image-capable chat endpoint and model')
        return await self._enqueue(messages, os.environ['PERSONA_QWEN_VISION_MODEL'], temperature,
                                   max_tokens, image_path=image_path)

    async def _enqueue(self, messages, model=None, temperature=0.2, max_tokens=1200, *, image_path=None):
        self.prompt_guard.assert_fits(messages, max_tokens)
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            if self._worker is not None and not self._worker.done():
                raise RuntimeError('GPU provider cannot span active event loops')
            self._loop, self._worker = loop, None
            self._fast_pending, self._slow_pending = deque(), deque()
        future = loop.create_future()
        fast = bool(messages and messages[0].get('content', '').startswith('FAST_STAGE:'))
        pending = self._fast_pending if fast else self._slow_pending
        args = (messages, model or self.model, temperature, max_tokens)
        if image_path is not None:
            args += (image_path,)
        pending.append((future, args, time.monotonic()))
        if self._worker is None or self._worker.done():
            self._worker = loop.create_task(self._dispatch(self._fast_pending, self._slow_pending))
        return await future

    async def _dispatch(self, fast, slow):
        # The remote server serializes generation with a lock. Keep its queue
        # local so interactive Fast calls can pass waiting Slow work. Reserve a
        # Slow turn after three Fast requests to avoid starving shared memory.
        fast_streak = 0
        try:
            while fast or slow:
                choose_fast = bool(fast) and (not slow or fast_streak < 3)
                future, args, queued_at = (fast if choose_fast else slow).popleft()
                if future.cancelled():
                    continue
                fast_streak = fast_streak + 1 if choose_fast else 0
                queue_ms = int((time.monotonic() - queued_at) * 1000)
                try:
                    content, usage = await asyncio.to_thread(self._complete, *args)
                except asyncio.CancelledError:
                    if not future.done():
                        future.cancel()
                    raise
                except Exception as exc:
                    if not future.done():
                        future.set_exception(exc)
                else:
                    if not future.done():
                        future.set_result((content, {**usage, 'provider_queue_ms': queue_ms}))
                # Let completed callers enqueue the next phase before dispatch.
                await asyncio.sleep(0)
        finally:
            for future, _, _ in [*fast, *slow]:
                if not future.done():
                    future.cancel()
            fast.clear(); slow.clear()

    @staticmethod
    def endpoint(url=None):
        url = url or os.environ.get("PERSONA_QWEN_API_URL", "http://127.0.0.1:8000/v1/chat/completions")
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.path != "/v1/chat/completions"
                or parsed.query or parsed.fragment or not parsed.port):
            raise ValueError("PERSONA_QWEN_API_URL은 로컬 SSH 터널의 /v1/chat/completions 주소여야 합니다")
        return url

    def health(self, *, url=None):
        url = self.endpoint(url).removesuffix('/v1/chat/completions') + '/health'
        with urllib.request.urlopen(url, timeout=2) as response:
            data = json.loads(response.read())
        if data.get('status') != 'ok' or data.get('model') != self.model:
            raise ValueError('GPU health의 상태 또는 모델명이 설정과 다릅니다')
        return data

    def _complete(self, messages, model, temperature, max_tokens, image_path=None):
        if image_path is not None:
            return self._complete_image(messages, model, temperature, max_tokens, image_path)
        if model != self.model:
            raise ValueError("GPU 서버 모델은 persona-qwen이어야 합니다")
        url = self.endpoint()
        self.prompt_guard.assert_fits(messages, max_tokens)
        body = json.dumps({"model": model, "messages": messages, "temperature": temperature,
                           "max_tokens": max_tokens, "response_format": {"type": "json_object"}},
                          ensure_ascii=False).encode()
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise RuntimeError(f"provider_http_{exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise ProviderConnectionError(_transport_error(exc)) from None
        usage = data.get("usage", {})
        return data["choices"][0]["message"]["content"], {
            "provider": "gpu", "model": data.get("model", model),
            "input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens")}

    async def embed(self, texts, model):
        raise ValueError("GPU 서버의 임베딩 API는 확인되지 않았습니다")

    def _complete_image(self, messages, model, temperature, max_tokens, image_path):
        # The existing text-only remote server is never assumed to accept images.
        url = self.endpoint(os.environ['PERSONA_QWEN_VISION_API_URL'])
        image_bytes = Path(image_path).read_bytes()
        if not image_bytes.startswith(b'\x89PNG\r\n\x1a\n') or len(image_bytes) > 8 * 1024 * 1024:
            raise RuntimeError('popup_image_invalid: expected a cropped PNG under 8 MiB')
        attached = [dict(message) for message in messages]
        index = next(i for i, message in enumerate(attached) if message['role'] == 'user')
        attached[index]['content'] = [
            {'type': 'text', 'text': attached[index]['content']},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(image_bytes).decode()}}]
        body = json.dumps({'model': model, 'messages': attached, 'temperature': temperature,
                           'max_tokens': min(max_tokens, 512), 'response_format': {'type': 'json_object'}},
                          ensure_ascii=False).encode()
        request = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            # Do not log a server response that might echo the image payload.
            raise RuntimeError(f'popup_vision_http_{exc.code}: image request rejected') from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise ProviderConnectionError(_transport_error(exc)) from None
        usage = data.get('usage', {})
        return data['choices'][0]['message']['content'], {
            'provider': 'gpu', 'model': data.get('model', model),
            'input_tokens': usage.get('prompt_tokens'), 'output_tokens': usage.get('completion_tokens'),
            'image_preflight': 'text_checked_image_tokens_not_counted'}
