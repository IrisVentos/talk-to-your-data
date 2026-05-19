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

from agent.data_loader import get_dataset, get_detailed_schema_text
from agent.query_store import get_by_id, to_prompt_text
from agent.models import AgentResult, QueryMatch
from agent.visualizer import detect_chart_request, generate_chart

# Conversation history for follow-up question support
_conversation_history: list[dict] = []
_MAX_HISTORY = 6  # keep last N exchanges

_CLASSIFY_PROMPT = """
You are a smart, flexible routing assistant for an internal FMCG data tool.
Your job is to understand what the user MEANS, even if they phrase it casually or briefly.

Available datasets (with column types and sample values):
{schema}

Validated query library:
{queries}

{history_block}
User question:
{question}

IMPORTANT GUIDELINES:
- Be GENEROUS in interpretation. Short questions like "revenue 2024" or "top products" are valid data questions.
- If a question mentions anything related to sales, revenue, products, categories, regions, channels, margins, employees, salary, attrition, performance, costs, EBITDA, or marketing — it IS in scope.
- Only mark as out_of_scope if the question is clearly unrelated (e.g. "what's the weather", "tell me a joke", "who is the president").
- When the user's intent is ambiguous but COULD relate to the data, attempt a new_query or multi_query rather than marking out_of_scope.
- Match existing queries generously: "revenue in 2024" maps to "monthly revenue trend", "best sellers" maps to "top products by revenue", etc.
- If the question requires data that might span multiple datasets, use multi_query to combine them.
- If a question asks about YoY growth, trends over years, or comparisons across time — check BOTH the financial dataset (which has YoY columns) AND the sales dataset (which has monthly transaction data). Use whichever has the relevant years.
- NEVER say out_of_scope for a business/data question. If the data might not exist, still generate a query — the system will handle the error gracefully.

Respond ONLY with valid JSON — no markdown, no explanation.

If the question is clearly unrelated to business/FMCG data:
{{"type": "out_of_scope"}}

If the user's question maps to an existing query (be generous — synonyms, abbreviations, partial matches all count):
{{"type": "matched", "matched_id": "<ID>"}}

If it is new but answerable from a SINGLE dataset:
{{
  "type": "new_query",
  "intent": "<short intent label, max 6 words>",
  "dataset": "<sales|hr|financial>",
  "description": "<one sentence>",
  "pandas_code": "<single pandas expression on variable df>"
}}

If the question requires data from MULTIPLE datasets (e.g. comparing revenue with HR data, or combining sales with financial KPIs):
{{
  "type": "multi_query",
  "intent": "<short intent label, max 6 words>",
  "description": "<one sentence>",
  "queries": [
    {{"dataset": "<dataset_name>", "pandas_code": "<expression on df>"}},
    {{"dataset": "<dataset_name>", "pandas_code": "<expression on df>"}}
  ],
  "merge_code": "<expression combining results_0, results_1, etc. using pd.merge or pd.concat>"
}}

Rules for pandas_code:
- Must be a single expression (no assignments, no imports).
- Variable df is the loaded DataFrame for that dataset.
- pandas is available as pd.
- Use exact column names from the schema above.
- For date/time filtering, use pd.to_datetime() and .dt accessor.
- For string matching, use .str.contains(..., case=False, na=False).
- Return a DataFrame or Series (not a scalar). Wrap scalars: pd.DataFrame({{'value': [expr]}}).
- When filtering by year/month, check if the column is datetime or string from the schema.

Rules for merge_code (multi_query only):
- Variables results_0, results_1, etc. are DataFrames from each query in order.
- Use pd.merge(), pd.concat(), or simple column operations to combine them.
- pandas is available as pd."""

_RETRY_PROMPT = """
The pandas code you generated failed with this error:
{error}

The dataset "{dataset}" has these columns:
{columns}

Here are the first 3 rows:
{sample_rows}

Please fix the pandas expression. Respond ONLY with valid JSON:
{{
  "type": "new_query",
  "intent": "{intent}",
  "dataset": "{dataset}",
  "description": "{description}",
  "pandas_code": "<corrected single pandas expression on variable df>"
}}
"""


def _strip_fences(text: str) -> str:
    return re.sub(r"^```[a-z]*\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()


def _history_block() -> str:
    """Format recent conversation for context."""
    if not _conversation_history:
        return ""
    lines = ["Recent conversation (for follow-up context):"]
    for entry in _conversation_history[-_MAX_HISTORY:]:
        lines.append(f"  User: {entry['question']}")
        lines.append(f"  Answer: {entry['answer'][:120]}")
    return "\n".join(lines) + "\n\n"


def classify(question: str, client: anthropic.Anthropic) -> QueryMatch:
    """Ask Claude to classify the question against the query library."""
    prompt = _CLASSIFY_PROMPT.format(
        schema=get_detailed_schema_text(),
        queries=to_prompt_text(),
        history_block=_history_block(),
        question=question,
    )
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = _strip_fences(response.content[0].text)
    return QueryMatch(**json.loads(raw))


def _retry_classify(error: str, match: QueryMatch, client: anthropic.Anthropic) -> QueryMatch:
    """Retry code generation by feeding the error back to Claude."""
    df = get_dataset(match.dataset)
    prompt = _RETRY_PROMPT.format(
        error=error,
        dataset=match.dataset,
        columns=", ".join(df.columns),
        sample_rows=df.head(3).to_string(index=False),
        intent=match.intent,
        description=match.description or "",
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
    elif not isinstance(result, pd.DataFrame):
        result = pd.DataFrame({"result": [result]})
    return result


def _summarise(df: pd.DataFrame, question: str, client: anthropic.Anthropic) -> str:
    """Generate a natural-language answer from the query results."""
    if df.empty:
        return "The query returned no results. The requested data may not be available in the current datasets."
    preview = df.head(10).to_string(index=False)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": (
                f"The user asked: \"{question}\"\n\n"
                f"Here are the data results:\n{preview}\n\n"
                "Provide a concise, friendly natural-language answer summarizing the key findings. "
                "Include specific numbers. Keep it to 2-3 sentences max. "
                "If the data doesn't fully answer the question (e.g. missing years or incomplete), "
                "mention what IS available and what's missing."
            )}],
        )
        return response.content[0].text.strip()
    except Exception:
        return f"Results ({len(df)} rows):\n{df.head(5).to_string(index=False)}"


def run(question: str, client: anthropic.Anthropic) -> AgentResult:
    """
    Full pipeline. Returns an AgentResult.

    When proposed_query is set, the caller should ask the user to validate
    and call query_store.add(result.proposed_query) if approved.
    """
    match = classify(question, client)

    # ── Out of scope ──────────────────────────────────────────────────────────
    if match.type == "out_of_scope":
        result = AgentResult(
            question=question,
            is_out_of_scope=True,
            answer=(
                "This question is outside the scope of the available datasets "
                "(Sales, HR, Financial KPIs). Please rephrase or ask something about "
                "revenue, products, employees, or financial performance."
            ),
        )
        _conversation_history.append({"question": question, "answer": result.answer})
        return result

    # ── Matched validated query ───────────────────────────────────────────────
    if match.type == "matched":
        query = get_by_id(match.matched_id)
        if not query:
            return AgentResult(
                question=question,
                answer=f"Query ID '{match.matched_id}' not found in the store.",
            )
        df = execute(query["pandas_code"], query["dataset"])
        answer = _summarise(df, question, client)
        chart_path = None
        if detect_chart_request(question):
            try:
                chart_path = generate_chart(df, question, intent=query.get("intent", ""))
            except Exception:
                pass
        _conversation_history.append({"question": question, "answer": answer})
        return AgentResult(
            question=question,
            query_id=query["id"],
            dataset=query["dataset"],
            pandas_code=query["pandas_code"],
            table=df.head(20).to_dict(orient="records"),
            answer=answer,
            chart_path=chart_path,
        )

    # ── New query — preview and propose for validation ────────────────────────
    if match.type == "new_query":
        proposed = {
            "intent": match.intent,
            "dataset": match.dataset,
            "description": match.description,
            "pandas_code": match.pandas_code,
        }
        # Try executing, with one retry on failure
        df = None
        table = None
        answer = None
        try:
            df = execute(match.pandas_code, match.dataset)
        except Exception as exc:
            # Retry: feed error back to Claude for a corrected query
            try:
                fixed_match = _retry_classify(str(exc), match, client)
                match = fixed_match
                proposed["pandas_code"] = match.pandas_code
                df = execute(match.pandas_code, match.dataset)
            except Exception as exc2:
                answer = f"Generated a query but execution failed after retry: {exc2}"

        chart_path = None
        if df is not None:
            table = df.head(20).to_dict(orient="records")
            answer = _summarise(df, question, client)
            if detect_chart_request(question):
                try:
                    chart_path = generate_chart(df, question, intent=match.intent or "")
                except Exception:
                    pass

        _conversation_history.append({"question": question, "answer": answer or ""})
        return AgentResult(
            question=question,
            dataset=match.dataset,
            pandas_code=match.pandas_code,
            table=table,
            proposed_query=proposed,
            answer=answer or "Could not generate results for this question.",
            chart_path=chart_path,
        )

    # ── Multi-dataset query ───────────────────────────────────────────────────
    if match.type == "multi_query":
        df = None
        table = None
        answer = None
        chart_path = None
        try:
            # Execute each sub-query
            results = {}
            for i, q in enumerate(match.queries):
                sub_df = execute(q["pandas_code"], q["dataset"])
                results[f"results_{i}"] = sub_df

            # Merge results
            namespace = {"__builtins__": {}, "pd": pd, **results}
            df = eval(match.merge_code, namespace)  # noqa: S307
            if isinstance(df, pd.Series):
                df = df.reset_index()
            elif not isinstance(df, pd.DataFrame):
                df = pd.DataFrame({"result": [df]})
        except Exception as exc:
            answer = f"Multi-dataset query failed: {exc}"

        if df is not None:
            table = df.head(20).to_dict(orient="records")
            answer = _summarise(df, question, client)
            if detect_chart_request(question):
                try:
                    chart_path = generate_chart(df, question, intent=match.intent or "")
                except Exception:
                    pass

        _conversation_history.append({"question": question, "answer": answer or ""})
        return AgentResult(
            question=question,
            dataset="multiple",
            pandas_code=match.merge_code,
            table=table,
            answer=answer or "Could not generate results for this question.",
            chart_path=chart_path,
        )

    return AgentResult(question=question, answer="Unexpected classification result.")