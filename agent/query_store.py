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
    # ── Sales (columns: Month, Product Name, Category, Region, Units Sold, Unit Price ($), Total Revenue ($), Discount (%), Net Revenue ($), Sales Rep)
    {
        "id": "S01",
        "intent": "total revenue by region",
        "dataset": "sales",
        "description": "Sum of Total Revenue ($) grouped by Region, sorted descending.",
        "pandas_code": "df.groupby('Region')['Total Revenue ($)'].sum().reset_index().sort_values('Total Revenue ($)', ascending=False)",
    },
    {
        "id": "S02",
        "intent": "total units sold by category",
        "dataset": "sales",
        "description": "Sum of Units Sold grouped by Category.",
        "pandas_code": "df.groupby('Category')['Units Sold'].sum().reset_index().sort_values('Units Sold', ascending=False)",
    },
    {
        "id": "S03",
        "intent": "top products by revenue",
        "dataset": "sales",
        "description": "Top 10 products ranked by total revenue.",
        "pandas_code": "df.groupby('Product Name')['Total Revenue ($)'].sum().reset_index().sort_values('Total Revenue ($)', ascending=False).head(10)",
    },
    {
        "id": "S04",
        "intent": "revenue by sales rep",
        "dataset": "sales",
        "description": "Revenue split by Sales Rep.",
        "pandas_code": "df.groupby('Sales Rep')['Total Revenue ($)'].sum().reset_index().sort_values('Total Revenue ($)', ascending=False)",
    },
    {
        "id": "S05",
        "intent": "average discount by category",
        "dataset": "sales",
        "description": "Average discount percentage per category.",
        "pandas_code": "df.groupby('Category')['Discount (%)'].mean().round(1).reset_index().sort_values('Discount (%)', ascending=False)",
    },
    {
        "id": "S06",
        "intent": "net revenue by category",
        "dataset": "sales",
        "description": "Total net revenue by category.",
        "pandas_code": "df.groupby('Category')['Net Revenue ($)'].sum().reset_index().sort_values('Net Revenue ($)', ascending=False)",
    },
    {
        "id": "S07",
        "intent": "monthly revenue trend",
        "dataset": "sales",
        "description": "Total revenue aggregated by month.",
        "pandas_code": "df.assign(Period=pd.to_datetime(df['Month']).dt.to_period('M').astype(str)).groupby('Period')['Total Revenue ($)'].sum().reset_index().sort_values('Period')",
    },
    {
        "id": "S08",
        "intent": "revenue by year",
        "dataset": "sales",
        "description": "Total revenue grouped by year.",
        "pandas_code": "df.assign(Year=pd.to_datetime(df['Month']).dt.year).groupby('Year')['Total Revenue ($)'].sum().reset_index().sort_values('Year')",
    },

    # ── HR (columns: Employee ID, Full Name, Department, Job Title, Contract Type, Start Date, Years at Company, Annual Salary ($), Bonus (%), Annual Bonus ($), Status)
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
        "description": "Mean Annual Salary ($) per department.",
        "pandas_code": "df.groupby('Department')['Annual Salary ($)'].mean().round(0).reset_index().sort_values('Annual Salary ($)', ascending=False)",
    },
    {
        "id": "H03",
        "intent": "employee status breakdown",
        "dataset": "hr",
        "description": "Count of employees by Status.",
        "pandas_code": "df.groupby('Status').size().reset_index(name='Count')",
    },
    {
        "id": "H04",
        "intent": "headcount by contract type",
        "dataset": "hr",
        "description": "Employee count by contract type.",
        "pandas_code": "df.groupby('Contract Type').size().reset_index(name='Count')",
    },
    {
        "id": "H05",
        "intent": "average bonus by department",
        "dataset": "hr",
        "description": "Mean Annual Bonus ($) per department.",
        "pandas_code": "df.groupby('Department')['Annual Bonus ($)'].mean().round(0).reset_index().sort_values('Annual Bonus ($)', ascending=False)",
    },
    {
        "id": "H06",
        "intent": "average tenure by department",
        "dataset": "hr",
        "description": "Average years at company per department.",
        "pandas_code": "df.groupby('Department')['Years at Company'].mean().round(1).reset_index().sort_values('Years at Company', ascending=False)",
    },

    # ── Financial (columns: Quarter, Gross Revenue ($), COGS ($), Gross Profit ($), Gross Margin (%), Operating Expenses ($), EBITDA ($), EBITDA Margin (%), Net Profit ($), Net Margin (%), YoY Revenue Growth (%))
    {
        "id": "F01",
        "intent": "gross margin by quarter",
        "dataset": "financial",
        "description": "Gross Margin (%) per quarter.",
        "pandas_code": "df[['Quarter', 'Gross Margin (%)']].sort_values('Quarter')",
    },
    {
        "id": "F02",
        "intent": "ebitda by quarter",
        "dataset": "financial",
        "description": "EBITDA ($) per quarter.",
        "pandas_code": "df[['Quarter', 'EBITDA ($)']].sort_values('Quarter')",
    },
    {
        "id": "F03",
        "intent": "quarterly net profit trend",
        "dataset": "financial",
        "description": "Net Profit ($) per quarter.",
        "pandas_code": "df[['Quarter', 'Net Profit ($)']].sort_values('Quarter')",
    },
    {
        "id": "F04",
        "intent": "operating expenses by quarter",
        "dataset": "financial",
        "description": "Operating Expenses ($) per quarter.",
        "pandas_code": "df[['Quarter', 'Operating Expenses ($)']].sort_values('Quarter')",
    },
    {
        "id": "F05",
        "intent": "year over year revenue growth",
        "dataset": "financial",
        "description": "YoY Revenue Growth (%) per quarter.",
        "pandas_code": "df[['Quarter', 'YoY Revenue Growth (%)']].sort_values('Quarter')",
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
        f"[{q['id']}] {q['intent']} — {q.get('description', '')} (dataset={q['dataset']})"
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