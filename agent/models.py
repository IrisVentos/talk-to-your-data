"""
models.py
---------
Pydantic models for agent input and output.
"""

from typing import Optional
from pydantic import BaseModel


class QueryMatch(BaseModel):
    """Claude's classification of a user question."""

    type: str  # "out_of_scope" | "matched" | "new_query" | "multi_query"

    # set when type == "matched"
    matched_id: Optional[str] = None

    # set when type == "new_query"
    intent: Optional[str] = None
    dataset: Optional[str] = None
    description: Optional[str] = None
    pandas_code: Optional[str] = None

    # set when type == "multi_query" (combines multiple datasets)
    queries: Optional[list[dict]] = None  # [{"dataset": ..., "pandas_code": ...}]
    merge_code: Optional[str] = None  # expression using results_0, results_1, etc.


class AgentResult(BaseModel):
    """Returned to the caller after the full pipeline runs."""

    question: str
    is_out_of_scope: bool = False

    # populated for matched or new queries
    query_id: Optional[str] = None      # None when new and not yet validated
    dataset: Optional[str] = None
    pandas_code: Optional[str] = None
    table: Optional[list[dict]] = None  # up to 20 rows

    # populated for new (unvalidated) queries
    proposed_query: Optional[dict] = None

    # populated when user requests a visualization
    chart_path: Optional[str] = None

    answer: str  # human-readable summary