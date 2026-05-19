# FMCG Talk-to-Your-Data Agent

Natural language querying over internal FMCG Excel datasets, powered by Claude AI and pydantic-ai.

## Structure

```
fmcg-data-agent/
├── agent/
│   ├── __init__.py        # public surface
│   ├── agent.py           # classify → execute → return pipeline
│   ├── data_loader.py     # Excel → pandas, cached
│   ├── models.py          # pydantic I/O models
│   └── query_store.py     # validated query library (seed + runtime additions)
├── data/                  # Excel files go here (not committed)
│   ├── sales.xlsx
│   ├── hr.xlsx
│   └── financial_kpis.xlsx
├── main.py                # CLI entry point
├── requirements.txt
└── .env.example
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env       # here to add the ANTHROPIC_API_KEY
```

Place your Excel files in `data/`. Column names must match what the seed
queries in `query_store.py` reference, or update the seed queries accordingly.

## Run

```bash
python main.py
```

## How it works

1. **Classify** — Claude sees the dataset schema and the validated query library,
   and returns one of three classifications:
   - `out_of_scope` → question has nothing to do with the datasets
   - `matched` → maps to an existing validated query (executed directly)
   - `new_query` → new intent; Claude generates a pandas expression

2. **Execute** — the pandas expression is evaluated against the relevant DataFrame.

3. **Validate** — for new queries, the user is shown the result and asked to
   approve. Approved queries are saved to `agent/validated_queries.json` and
   reused in future sessions.

## Extending

- **New dataset**: add an entry to `DATASETS` in `data_loader.py` and seed
  queries in `query_store.py`.
- **System prompt**: edit `_CLASSIFY_PROMPT` in `agent/agent.py`.
- **Web / API layer**: import `run` and `save_query` from the `agent` package
  and wire them to your preferred framework.