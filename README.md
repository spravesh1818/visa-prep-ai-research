# Ontology-Driven Visa Interviewer

A multi-turn, **ontology-driven** mock visa interviewer built with **FastAPI** and
**LangGraph**. It conducts a realistic consular-style interview, dynamically
generates human-sounding questions (never hardcoded), probes answers when
something looks off, credibility-checks the university the applicant names, and
produces a detailed scored report for a backend to deliver to users.

> Disclaimer: this is a preparation / mock tool. It is **not** an official visa
> adjudication and does not predict any government decision.

## Highlights

- **Ontology-driven**: each country + visa type is a structured YAML ontology of
  *intents*, expected signals, red flags, probe triggers, weights, and
  cross-answer consistency rules. No literal questions are stored anywhere.
- **Human-like, non-scripted questions**: greetings, questions, and probes are
  generated from intent + live conversation, with explicit anti-script
  instructions so wording varies every time.
- **Adaptive probing**: each answer is evaluated (signals, red flags,
  contradictions, vagueness, coaching) and followed up when warranted.
- **University credibility**: spoken university names are matched against a
  registry of ~3,000 US + UK institutions (IPEDS + Hipolabs) with curated tier
  overrides; high tiers raise the score, low tiers / diploma mills lower it.
- **Detailed report**: per-topic scores, red flags, consistency findings,
  university assessment, strengths/weaknesses, probing summary, and full
  transcript - returned via API and optionally POSTed to your backend.
- **Central, swappable LLM**: one env-driven factory supports **OpenAI,
  Anthropic, Google Gemini, local/Ollama, DeepSeek, and Moonshot (Kimi)**, so you
  can A/B different models.
- **Real-time voice mode (optional)**: a LiveKit Cloud voice agent (Deepgram STT
  + ElevenLabs TTS) speaks the officer's turns and transcribes the applicant,
  driving the *same* LangGraph interview via a custom LLM adapter. A small
  React client (`frontend/`) provides the UI.

## Architecture

```
FastAPI (app/api) ──> LangGraph interview graph (app/interview)
                         ├─ LLM factory (app/llm)        env-driven, multi-provider
                         ├─ Ontology (app/ontology)      YAML -> Pydantic
                         ├─ University service (app/knowledge)  curated tiers + fuzzy match
                         ├─ Scoring + Report (app/interview)
                         └─ Checkpointer (app/session)   thread_id == session_id
```

Interview graph:

```
initialize -> greet -> ask_question -> await_answer -> evaluate_answer
                                  ^                          |
              probe <------------ |  (needs probe)  --------/
                                  |  (more topics) -> next_topic -> ask_question
                                  |  (done)        -> finalize -> END
```

Multi-turn works via LangGraph `interrupt()` inside `await_answer`; the API
resumes with `Command(resume=<applicant answer>)` keyed by the session's
`thread_id`.

## Setup

```bash
# install deps (uses uv)
uv sync

# configure environment
cp .env.example .env
# edit .env: set LLM_PROVIDER, LLM_MODEL, and the matching API key
```

Run the API:

```bash
uv run python main.py
# or: uv run uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for interactive Swagger UI.

## API

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET  | `/health` | Liveness check |
| GET  | `/config` | Active LLM, checkpointer, supported interviews, `voice_enabled` |
| POST | `/interview/start` | Start an interview, returns greeting + first question |
| POST | `/interview/{session_id}/respond` | Submit an answer, get the next officer message |
| GET  | `/interview/{session_id}/report` | Fetch the detailed report once complete |
| POST | `/voice/token` | Mint a LiveKit token for the voice client (requires voice config) |

Example:

```bash
# Start
curl -s localhost:8000/interview/start -H 'content-type: application/json' \
  -d '{"country":"US","visa_type":"F1","candidate_profile":{"name":"Asha"}}'

# Respond (repeat until status == "completed")
curl -s localhost:8000/interview/<session_id>/respond \
  -H 'content-type: application/json' -d '{"message":"I will study CS at MIT..."}'

# Report
curl -s localhost:8000/interview/<session_id>/report
```

If `REPORT_WEBHOOK_URL` is set, the completed report is also POSTed there
automatically for your backend to ingest.

## Supported interviews

US `F1`, US `J1`, US `B1B2`, US `H1B`, and UK `Student`. Country/visa lookup is
formatting-tolerant (`us`/`US`, `f1`/`F-1`).

### Adding a new country / visa type

Drop a new YAML file in `app/ontology/data/` following the existing schema
(`country`, `visa_type`, `officer_persona`, `topics[]`, `consistency_rules`).
It is picked up automatically - no code changes needed.

## Configuration (`.env`)

Key settings (see `.env.example` for all):

- `LLM_PROVIDER` = `openai` | `anthropic` | `google` | `ollama` | `deepseek` | `moonshot`
- `LLM_MODEL`, `LLM_TEMPERATURE`, optional per-role `INTERVIEWER_*` / `EVALUATOR_*`
- `CHECKPOINTER_BACKEND` = `sqlite` (default) | `memory`
- `MAX_PROBES_PER_TOPIC`
- `REPORT_WEBHOOK_URL`, `LANGSMITH_TRACING`, `COST_*` voice infra rates

### Per-interview cost in LangSmith

Enable `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in `.env`, then restart the
API and voice worker. Each interview's `session_id` is the LangSmith **thread id**.

1. Open [LangSmith](https://smith.langchain.com) → project `visa-interviewer` → **Threads**.
2. Select the thread matching your interview `session_id`.
3. **LLM cost** is traced automatically from LangGraph.
4. **Voice infra** (Deepgram STT, Cartesia TTS, LiveKit minutes) is estimated at
   session shutdown and pushed as `interview_voice_cost` runs on the same thread.

Tune `COST_DEEPGRAM_STT_USD_PER_MIN`, `COST_CARTESIA_TTS_USD_PER_MIN`, and
`COST_LIVEKIT_AGENT_USD_PER_MIN` against your provider invoices.

> `memory` checkpointer is dev-only (not shared across uvicorn workers). Use
> `sqlite` for a single worker, or swap in `PostgresSaver` for multi-worker
> production - the graph code is checkpointer-agnostic.

## University registry

University credibility uses `app/knowledge/universities.json`, a generated registry
of ~3,000 US (IPEDS, active 4-year) and UK (Hipolabs) institutions. Each school is
matched by exact-normalized name first (robust), then fuzzy fallback for typos.

Tiers and their effect on the score:

| Tier | Meaning | Score effect |
| ---- | ------- | ------------ |
| `top` / `high` / `mid` | Curated ranking-based tiers | strong/positive |
| `recognized` | Accredited but not separately ranked (registry default) | neutral (0) |
| `low` | Weaker reputation | negative |
| `diploma_mill` | Known fraudulent institution | strong negative |
| `unknown` | Not found in the registry | mild caution |

Ranking-based tiers live in `app/knowledge/curated_overrides.json` (hand-maintained).
To rebuild the registry (e.g. to refresh data or add curated tiers):

```bash
uv run python scripts/build_universities.py            # download fresh sources
# or, offline, point at local copies:
uv run python scripts/build_universities.py --ipeds /path/HD2023.csv --hipolabs /path/world.json
```

The official UK "register of licensed student sponsors" CSV can be substituted for
the UK source in the script if you need the authoritative sponsor list.

## LLM providers (incl. DeepSeek & Kimi)

Set `LLM_PROVIDER` + `LLM_MODEL` and the matching key:

| Provider | `LLM_PROVIDER` | Example `LLM_MODEL` | Key |
| -------- | -------------- | ------------------- | --- |
| OpenAI | `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `anthropic` | `claude-3-5-sonnet-latest` | `ANTHROPIC_API_KEY` |
| Google | `google` | `gemini-1.5-flash` | `GOOGLE_API_KEY` |
| Ollama (local) | `ollama` | `llama3.1` | — (`OLLAMA_BASE_URL`) |
| DeepSeek | `deepseek` | `deepseek-chat` | `DEEPSEEK_API_KEY` |
| Moonshot (Kimi) | `moonshot` | `kimi-k2.5` | `MOONSHOT_API_KEY` |

> Use DeepSeek `deepseek-chat` (V3), **not** `deepseek-reasoner` (R1 lacks tool
> calling / structured output). Structured outputs are provider-aware: OpenAI
> uses strict `json_schema`; the others use `function_calling`.

## Prompt templates

Officer utterances are built from versioned YAML templates under
`app/interview/prompts/{version}/{provider}/`. Set:

- `PROMPT_VERSION=v1` — which template set to load (default `v1`)
- `LLM_PROVIDER` — selects provider-specific overrides when present (e.g.
  `v1/google/greeting.yaml`), otherwise falls back to `v1/default/`

Edit YAML to tune wording per provider without changing Python code.

## Ontology timezones

Each ontology YAML (`app/ontology/data/*.yaml`) may define `timezone` (IANA,
e.g. `Europe/London`, `America/New_York`). The officer greeting uses the local
time at that consular window so "good morning" matches the actual time of day.

## Voice latency tuning

The voice agent is optimized for responsiveness:

- `VOICE_FAST_MODE=true` (default) — one interviewer LLM call per spoken turn;
  structured evaluation runs in a background thread so TTS starts sooner.
  Probing triggered by evaluation applies on the **next** officer turn.
- `VOICE_MIN_ENDPOINTING_DELAY` / `VOICE_MAX_ENDPOINTING_DELAY` — how long
  to wait after you stop speaking (defaults `0.6` / `3.0` seconds).
- `DEEPGRAM_ENDPOINTING_MS` — STT silence detection (default `300`).
- Use fast, stable models for voice (`gpt-4o-mini`, `gemini-2.5-flash`); avoid
  overloaded preview models that return 503 retries.
- Optional role split: `INTERVIEWER_MODEL` (creative) + `EVALUATOR_MODEL`
  (cheap/deterministic).
- Keep the voice worker running to avoid LiveKit cold starts.
- Enable `LANGSMITH_TRACING=true` and search logs for `voice_timing` to see
  phase durations (`start_interview`, `graph_done`, `tts_start`).

Opening greeting and first question are spoken as **separate** TTS utterances
(split on blank lines) so the first audio starts sooner.

## Voice interview (LiveKit + Deepgram + Cartesia)

The voice layer reuses the entire LangGraph brain (ontology, probing, university
checks, scoring) via a custom LiveKit `LLM` adapter; only the I/O changes to
speech.

1. Configure keys in `.env`: `LIVEKIT_URL`, `LIVEKIT_API_KEY`,
   `LIVEKIT_API_SECRET` (LiveKit Cloud), `DEEPGRAM_API_KEY`,
   `ELEVENLABS_API_KEY` (and optionally `ELEVENLABS_VOICE_ID`).
2. Start the API: `uv run python main.py`
3. Start the voice agent worker: `uv run python -m app.voice.agent dev`
4. Start the React client:

   ```bash
   cd frontend && npm install && npm run dev   # http://localhost:5173
   ```

Pick a visa type, click **Start voice interview**, and speak. The officer's
greeting/questions are spoken (Cartesia TTS by default), your answers are
transcribed (Deepgram), live transcripts render in the UI, and the scored
report appears automatically when the interview ends. See `frontend/README.md`
for details.

The text API and offline tests keep working without any voice keys.

## Comparing models

```bash
uv run python scripts/compare_models.py --country US --visa F1 \
  --model openai:gpt-4o-mini --model anthropic:claude-3-5-sonnet-latest \
  --model deepseek:deepseek-chat --model moonshot:kimi-k2.5
```

Feeds an identical scripted interview to each model and prints a score
comparison.

## Tests

```bash
uv run pytest
```

Tests run fully offline (a fake LLM replaces all model calls).
