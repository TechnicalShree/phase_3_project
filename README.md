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
