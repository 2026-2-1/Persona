# UXAgent

UXAgent runs persona-based tasks against a local browser page and records observations, actions, evaluator results, and screenshots. Simulated answers and issue candidates are research aids; they do not represent real user reports or validated human behavior.

## Setup

Requires Python 3.11+ and a Playwright-supported local OS. On macOS, Linux, or Windows:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m playwright install chromium
python -m uxagent doctor --study configs/study.json
```

The default mock run uses no key and follows a deterministic path through the local fixture. For `--provider jev`, put `TYPESAFE_API_KEY` and `GEMINI_API_KEY` in a root `.env` file (see `.env.example`). The runner loads `.env` without overriding variables already present in the process environment. Jev (`jev-latest`) ranks code-generated actions from visible, enabled elements; Gemini `gemini-2.5-flash-lite` runs only when Jev confidence is below 0.65, returns an invalid choice, fails, or the page has no supported candidates. Use `--provider gemini` to run Gemini directly. `--provider live` retains the existing OpenAI provider.

Each model request is recorded in `llm_calls.jsonl` with provider, model, elapsed time, token counts, cost estimate, error status, and fallback reason. `summary.json` groups request counts, tokens, and estimated cost by provider. Gemini estimates use the current paid text rates ($0.10/1M input and $0.40/1M output); actual free-tier billing may be zero. Jev estimates use TypeSafe's published $0.042/1M input-token rate and free output tokens. Missing usage is marked estimated and has unknown cost.

Gemini 2.5 Flash-Lite's current free tier lists text input and output as free, but says free-tier prompts may be used to improve Google products; paid-tier prompts are not used for that purpose under the published pricing terms. Exact RPM/TPM/RPD quotas are per account and shown in AI Studio; they can change, so check the project's active limits there. Jev is in early access, with account access and limits controlled in the TypeSafe console; TypeSafe's privacy policy says it does not train on API inputs, while its policy says data is retained as reasonably necessary and its agreement allows telemetry derived from customer data to be retained. No guaranteed public Jev free-use quota is stated. The agent sends the current observation, task, and limited recent memory to the selected provider.

Provider references: [TypeSafe System One API](https://docs.typesafe.ai/api), [TypeSafe privacy policy](https://typesafe.ai/legal/privacy-policy), [TypeSafe pricing announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev), [Gemini pricing and free-tier data use](https://ai.google.dev/gemini-api/docs/pricing), and [Gemini billing and quota guidance](https://ai.google.dev/gemini-api/docs/billing).

## Run

```sh
python -m uxagent run --study configs/study.json --provider mock --headless
python -m uxagent run --study configs/study.json --provider jev --headless
python -m uxagent observe --study configs/study.json --headless
python -m uxagent review --run runs/<run_id>
python -m uxagent survey --run runs/<run_id>
python -m uxagent interview --run runs/<run_id> --at-step 4 --question "이때 어떤 정보를 찾고 있었나요?"
```

Run artifacts are written under `runs/<run_id>/`. To view the fixture directly, run `python -m uxagent serve`; it serves `tests/fixtures` at `http://127.0.0.1:8000`.

## Personas and batch

```sh
python -m uxagent personas --config configs/personas.json
python -m uxagent batch --study configs/study.json --personas personas.jsonl --provider mock
```

Batch execution is sequential and creates a new browser context per persona. Persona generation uses a seeded local template and reports its provenance; it does not call an LLM.

## Dashboard

Open the local dashboard to generate personas, run them sequentially, and follow each persona's latest page screenshot, URL, action timeline, and model-call usage:

```sh
python3 -m uxagent dashboard
```

Then visit `http://127.0.0.1:8765`:

1. Enter the website URL, task, persona description, and number of personas (1–12).
2. Click **페르소나 생성**. The free local template uses your description and task, varies exploration habits and digital familiarity, and records the generation seed and time.
3. Choose **Jev 우선** or **Gemini 직접** for external websites, then click **순차 테스트 시작**. **Mock** is for the bundled shop fixture; **기본 데모 설정** prepares that example with two personas.
4. Follow the current persona's logs, model calls, page URL, and latest screenshot. Select a persona or stored run to inspect it, or click a step to see its recorded screen. **현재 실행 따라가기** follows the running batch again.

The dashboard reads existing `runs/` artifacts, including runs in subdirectories, and stores generated personas under `runs/personas/`. Each job saves its configuration under `runs/.dashboard/` with an absolute persona path. Job failures display a reason; API key values are never returned to the page. Form values are saved in the local browser after starting a job.

The server binds to localhost. Screenshots appear after the browser records an observation. External websites do not have a task-specific evaluator, so an agent's completion judgment is not automatically a verified success. Navigation remains restricted to the entered website's origin.

## Scope

Observation is viewport-based. Iframes, canvas controls, complex shadow DOM, custom comboboxes, and password fields are unsupported. The executor validates all target IDs against the newest observation. The local fixture evaluator runs independently from the model prompt. Live provider support uses the OpenAI Chat Completions API and requires an explicit live flag.
