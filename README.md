# Campus IT Desk — Phase 3

**Domain: Campus IT Helpdesk (Option 1).** LangGraph orchestration with a local mock campus service desk. Repo-only submission; Python 3.12+, no Docker required.

## Setup

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m unittest discover -s tests -v
```

`MODEL_MODE=demo` uses deterministic offline decisions, not an LLM. For live classification set `MODEL_MODE=live`, `OPENAI_API_KEY` and optionally `OPENAI_MODEL` / `OPENAI_BASE_URL` in `.env`. Real credentials are never committed.

## Incremental build

Each row corresponds to a tested implementation commit, not a retrospective label.

| Stage | Capability | Check |
| --- | --- | --- |
| 1 | Typed StateGraph and conditional category routing; live structured classification | Four category routing cases |
| 2 | Three bound lookup tools and a real ToolNode loop | Tool call names and campus facts verified |
| 3 | ReAct iteration cap and duplicate tool fingerprint detection | Adversarial model doubles stop without timeout |
| 4 | SQLite checkpoints, thread IDs, run/stream entry points | Separate Python processes continue the same conversation |
| 5 | Bounded extractive summary and message/history trimming | Seven turns shrink to two plus a summary |
| 6 | PII masking before checkpoints/model calls; injection and off-topic blocking; egress scan | Zero model calls for blocked input; no sample PII in checkpoints |
| 7 | Independently compiled triage/research subgraphs and findings reducer | Subgraphs invoked outside the master graph |
| 8 | Structured supervisor, worker return paths, delegation cap | research → specialist → FINISH; cap precedes model call |
| 9 | Send fan-out to three compiled specialists and synthesis | Three-party barrier proves concurrent execution; irrelevant advice filtered |
