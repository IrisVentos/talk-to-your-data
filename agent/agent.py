"""
agent.py
--------
Core agent pipeline.

Flow:
  1. classify()  — ask Claude to match the question to the query library
                   or generate a new pandas expression
  2. execute()   — run the pandas code against the Excel dataset
  3. run()       — full pipeline, returns AgentResult

Validation of new queries is the caller's responsibility
(CLI, web handler, etc.) via query_store.add().
"""

import json
import re
import pandas as pd
import anthropic

from agent.data_loader import get_dataset, get_schema_text
from agent.query_store import get_by_id, to_prompt_text
from agent.models import AgentResult, QueryMatch

_CLASSIFY_PROMPT = """
You are a routing assistant for an internal data tool.

Available datasets and their columns:
{schema}

Validated query library:
{queries}

User question:
{question}

Respond ONLY with valid JSON — no markdown, no explanation.

If the question is unrelated to the datasets:
{{"type": "out_of_scope"}}

If it matches an existing query:
{{"type": "matched", "matched_id": "<ID>"}}

If it is new but answerable from the data:
{{
  "type": "new_query",
  "intent": "<short intent label, max 6 words>",
  "dataset": "<sales|hr|financial>",
  "description": "<one sentence>",
  "pandas_code": "<single pandas expression on variable df>"
}}

Rules for pandas_code:
- Must be a single expression (no assignments, no imports).
- Variable df is the loaded DataFrame.
- pandas is available as pd.
"""


def _strip_fences(text: str) -> str:
    return re.sub(r"^```[a-z]*\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()


def classify(question: str, client: anthropic.Anthropic) -> QueryMatch:
    """Ask Claude to classify the question against the query library."""
    prompt = _CLASSIFY_PROMPT.format(
        schema=get_schema_text(),
        queries=to_prompt_text(),
        question=question,
    )
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = _strip_fences(response.content[0].text)
    return QueryMatch(**json.loads(raw))


def execute(pandas_code: str, dataset: str) -> pd.DataFrame:
    """Evaluate a pandas expression against the named dataset."""
    df = get_dataset(dataset)
    result = eval(pandas_code, {"__builtins__": {}, "pd": pd}, {"df": df})  # noqa: S307
    if isinstance(result, pd.Series):
        result = result.reset_index()
    return result


def _summarise(df: pd.DataFrame, intent: str) -> str:
    if df.empty:
        return "The query returned no results."
    preview = df.head(5).to_string(index=False)
    return f"Results for '{intent}':\n{preview}"


def run(question: str, client: anthropic.Anthropic) -> AgentResult:
    """
    Full pipeline. Returns an AgentResult.

    When proposed_query is set, the caller should ask the user to validate
    and call query_store.add(result.proposed_query) if approved.
    """
    match = classify(question, client)

    # ── Out of scope ──────────────────────────────────────────────────────────
    if match.type == "out_of_scope":
        return AgentResult(
            question=question,
            is_out_of_scope=True,
            answer=(
                "This question is outside the scope of the available datasets "
                "(Sales, HR, Financial KPIs). Please rephrase or contact the relevant team."
            ),
        )

    # ── Matched validated query ───────────────────────────────────────────────
    if match.type == "matched":
        query = get_by_id(match.matched_id)
        if not query:
            return AgentResult(
                question=question,
                answer=f"Query ID '{match.matched_id}' not found in the store.",
            )
        df = execute(query["pandas_code"], query["dataset"])
        return AgentResult(
            question=question,
            query_id=query["id"],
            dataset=query["dataset"],
            pandas_code=query["pandas_code"],
            table=df.head(20).to_dict(orient="records"),
            answer=_summarise(df, query["intent"]),
        )

    # ── New query — preview and propose for validation ────────────────────────
    if match.type == "new_query":
        proposed = {
            "intent": match.intent,
            "dataset": match.dataset,
            "description": match.description,
            "pandas_code": match.pandas_code,
        }
        try:
            df = execute(match.pandas_code, match.dataset)
            table = df.head(20).to_dict(orient="records")
            answer = _summarise(df, match.intent)
        except Exception as exc:
            table = None
            answer = f"Generated a new query but preview failed: {exc}"

        return AgentResult(
            question=question,
            dataset=match.dataset,
            pandas_code=match.pandas_code,
            table=table,
            proposed_query=proposed,
            answer=answer,
        )

    return AgentResult(question=question, answer="Unexpected classification result.")