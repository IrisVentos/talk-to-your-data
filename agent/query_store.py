"""
query_store.py
--------------
Manages the library of validated query patterns.

On first run, the store is seeded from SEED_QUERIES.
New queries validated by users at runtime are appended and persisted to
validated_queries.json (next to this file), so they survive restarts.

Each query record:
    id          - auto-assigned (e.g. S03, H02, F01)
    intent      - short label used for semantic matching
    dataset     - one of: sales | hr | financial
    description - one sentence explaining what it computes
    pandas_code - single-line expression evaluated on DataFrame `df`
"""

import json
import os

_STORE_PATH = os.path.join(os.path.dirname(__file__), "validated_queries.json")

SEED_QUERIES: list[dict] = [
    # ── Sales ──────────────────────────────────────────────────────────
    {
        "id": "S01",
        "intent": "total revenue by region",
        "dataset": "sales",
        "description": "Sum of Revenue_EUR grouped by Region, sorted descending.",
        "pandas_code": "df.groupby('Region')['Revenue_EUR'].sum().reset_index().sort_values('Revenue_EUR', ascending=False)",
    },
    {
        "id": "S02",
        "intent": "total units sold by category",
        "dataset": "sales",
        "description": "Sum of Units_Sold grouped by Category.",
        "pandas_code": "df.groupby('Category')['Units_Sold'].sum().reset_index().sort_values('Units_Sold', ascending=False)",
    },
    {
        "id": "S03",
        "intent": "top products by revenue",
        "dataset": "sales",
        "description": "Top 10 products ranked by total Revenue_EUR.",
        "pandas_code": "df.groupby('Product_Name')['Revenue_EUR'].sum().reset_index().sort_values('Revenue_EUR', ascending=False).head(10)",
    },
    {
        "id": "S04",
        "intent": "revenue by channel",
        "dataset": "sales",
        "description": "Revenue split by sales Channel.",
        "pandas_code": "df.groupby('Channel')['Revenue_EUR'].sum().reset_index().sort_values('Revenue_EUR', ascending=False)",
    },
    {
        "id": "S05",
        "intent": "promotional impact on revenue",
        "dataset": "sales",
        "description": "Average revenue and units for promoted vs non-promoted sales.",
        "pandas_code": "df.groupby('Promo_Flag')[['Revenue_EUR', 'Units_Sold']].mean().reset_index()",
    },
    {
        "id": "S06",
        "intent": "gross margin by category",
        "dataset": "sales",
        "description": "Total gross margin EUR by category.",
        "pandas_code": "df.groupby('Category')['Gross_Margin_EUR'].sum().reset_index().sort_values('Gross_Margin_EUR', ascending=False)",
    },
    {
        "id": "S07",
        "intent": "monthly revenue trend",
        "dataset": "sales",
        "description": "Revenue aggregated by month.",
        "pandas_code": "df.assign(Month=pd.to_datetime(df['Date']).dt.to_period('M').astype(str)).groupby('Month')['Revenue_EUR'].sum().reset_index().sort_values('Month')",
    },

    # ── HR ─────────────────────────────────────────────────────────────
    {
        "id": "H01",
        "intent": "headcount by department",
        "dataset": "hr",
        "description": "Number of employees per department.",
        "pandas_code": "df.groupby('Department').size().reset_index(name='Headcount').sort_values('Headcount', ascending=False)",
    },
    {
        "id": "H02",
        "intent": "average salary by department",
        "dataset": "hr",
        "description": "Mean Salary_EUR per department.",
        "pandas_code": "df.groupby('Department')['Salary_EUR'].mean().round(0).reset_index().sort_values('Salary_EUR', ascending=False)",
    },
    {
        "id": "H03",
        "intent": "attrition rate by department",
        "dataset": "hr",
        "description": "Attrition rate (%) per department.",
        "pandas_code": "df.groupby('Department')['Attrition'].mean().mul(100).round(1).reset_index().rename(columns={'Attrition': 'Attrition_Rate_Pct'}).sort_values('Attrition_Rate_Pct', ascending=False)",
    },
    {
        "id": "H04",
        "intent": "gender diversity breakdown",
        "dataset": "hr",
        "description": "Employee count by gender.",
        "pandas_code": "df.groupby('Gender').size().reset_index(name='Count')",
    },
    {
        "id": "H05",
        "intent": "average performance score by department",
        "dataset": "hr",
        "description": "Mean performance score per department.",
        "pandas_code": "df.groupby('Department')['Performance_Score'].mean().round(2).reset_index().sort_values('Performance_Score', ascending=False)",
    },
    {
        "id": "H06",
        "intent": "headcount by country",
        "dataset": "hr",
        "description": "Number of employees per country.",
        "pandas_code": "df.groupby('Country').size().reset_index(name='Headcount').sort_values('Headcount', ascending=False)",
    },

    # ── Financial ──────────────────────────────────────────────────────
    {
        "id": "F01",
        "intent": "gross margin by region",
        "dataset": "financial",
        "description": "Average Gross_Margin_Pct by region.",
        "pandas_code": "df.groupby('Region')['Gross_Margin_Pct'].mean().round(1).reset_index().sort_values('Gross_Margin_Pct', ascending=False)",
    },
    {
        "id": "F02",
        "intent": "ebitda by category",
        "dataset": "financial",
        "description": "Total EBITDA_EUR by category.",
        "pandas_code": "df.groupby('Category')['EBITDA_EUR'].sum().reset_index().sort_values('EBITDA_EUR', ascending=False)",
    },
    {
        "id": "F03",
        "intent": "monthly net revenue trend",
        "dataset": "financial",
        "description": "Total net revenue per month.",
        "pandas_code": "df.groupby('Month')['Net_Revenue_EUR'].sum().reset_index().sort_values('Month')",
    },
    {
        "id": "F04",
        "intent": "marketing spend as percent of revenue by category",
        "dataset": "financial",
        "description": "Marketing spend efficiency per category.",
        "pandas_code": "df.groupby('Category').apply(lambda x: (x['Marketing_Spend_EUR'].sum() / x['Net_Revenue_EUR'].sum() * 100).round(1)).reset_index(name='Marketing_Pct_Revenue')",
    },
    {
        "id": "F05",
        "intent": "operating costs by region",
        "dataset": "financial",
        "description": "Total operating costs per region.",
        "pandas_code": "df.groupby('Region')['Operating_Costs_EUR'].sum().reset_index().sort_values('Operating_Costs_EUR', ascending=False)",
    },
]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load() -> list[dict]:
    if os.path.exists(_STORE_PATH):
        with open(_STORE_PATH) as f:
            return json.load(f)
    return list(SEED_QUERIES)


def _save(queries: list[dict]) -> None:
    with open(_STORE_PATH, "w") as f:
        json.dump(queries, f, indent=2)


# ── Public API ────────────────────────────────────────────────────────────────

def get_all() -> list[dict]:
    return _load()


def get_by_id(query_id: str) -> dict | None:
    return next((q for q in get_all() if q["id"] == query_id), None)


def to_prompt_text() -> str:
    """Compact listing for inclusion in Claude prompts."""
    return "\n".join(
        f"[{q['id']}] {q['intent']} (dataset={q['dataset']})"
        for q in get_all()
    )


def add(query: dict) -> str:
    """
    Persist a new validated query. Auto-assigns an ID.
    Returns the assigned ID.
    """
    queries = get_all()
    prefix = query.get("dataset", "X")[0].upper()
    taken = {int(q["id"][1:]) for q in queries if q["id"][0] == prefix and q["id"][1:].isdigit()}
    next_n = next(n for n in range(1, 999) if n not in taken)
    query["id"] = f"{prefix}{next_n:02d}"
    queries.append(query)
    _save(queries)
    return query["id"]