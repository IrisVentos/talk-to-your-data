# FMCG Talk-to-Your-Data Agent

Natural-language querying over internal FMCG Excel datasets, powered by Claude AI.

## Features

- **Natural language interface** — ask questions in plain English, even casually ("revenue 2024", "best sellers")
- **Smart query matching** — maps questions to a library of validated queries, or generates new pandas code on-the-fly
- **Multi-dataset support** — can combine data from Sales, HR, and Financial KPIs in a single answer
- **Auto-retry** — if generated code fails, the error is fed back to Claude for self-correction
- **Conversation memory** — supports follow-up questions with context from recent exchanges
- **Visualizations** — generates charts (bar, line, pie) when you ask for graphs or plots
- **Validated query library** — approved queries are saved and reused for consistency

## Structure

```
talk-to-your-data/
├── agent/
│   ├── __init__.py            # public API surface
│   ├── agent.py               # classify → execute → summarise pipeline
│   ├── data_loader.py         # Excel → pandas (multi-sheet, cached)
│   ├── models.py              # Pydantic I/O models
│   ├── query_store.py         # validated query library (seed + runtime)
│   ├── validated_queries.json # persisted approved queries
│   └── visualizer.py          # chart generation (matplotlib)
├── data/
│   └── pernod_agent.xlsx      # Excel workbook with sheets: Sales, HR, Financial_KPIs
├── charts/                    # generated chart PNGs (auto-created)
├── main.py                    # CLI entry point
├── requirements.txt
└── .env                       # ANTHROPIC_API_KEY token goes here
```

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file at the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Place the Excel workbook at `data/pernod_agent.xlsx`.

## Run

```bash
python main.py
```

### Example questions

- "What is the total revenue by region?"
- "Show me the top 5 products by revenue"
- "Average salary by department"
- "Build a chart of revenue over the months"
- "Compare EBITDA across quarters"
- "YoY revenue growth"

## How it works

1. **Classify** — Claude sees the detailed dataset schema (column types, sample values) and the validated query library, then returns one of:
   - `out_of_scope` → clearly unrelated to business data
   - `matched` → maps to an existing validated query (executed directly)
   - `new_query` → generates a pandas expression for a single dataset
   - `multi_query` → generates queries across multiple datasets and merges them

2. **Execute** — the pandas expression is evaluated against the relevant DataFrame(s). Scalar results are wrapped into DataFrames automatically.

3. **Retry** — if execution fails, the error and actual column names are sent back to Claude for a corrected attempt.

4. **Summarise** — Claude generates a concise natural-language answer from the results.

5. **Visualize** — if the user asked for a chart/graph/plot, a PNG is generated and saved to `charts/`.

6. **Validate** — for new queries, the user is shown the result and asked to approve. Approved queries are saved to `agent/validated_queries.json` and reused in future sessions.

## Extending

- **New dataset**: add a sheet to the Excel workbook and an entry to `DATASETS` in `data_loader.py`.
- **New seed queries**: add entries to `SEED_QUERIES` in `query_store.py` (used as fallback if JSON is deleted).
- **System prompt**: edit `_CLASSIFY_PROMPT` in `agent/agent.py`.
- **Web / API layer**: import `run` and `save_query` from the `agent` package and wire them to your preferred framework.

## Dependencies

- `anthropic` — Claude API client
- `pandas` + `openpyxl` — data loading and manipulation
- `matplotlib` — chart generation
- `python-dotenv` — environment variable management
- `pydantic` — data validation models