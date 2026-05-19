"""
data_loader.py
--------------
Loads Excel datasets into pandas DataFrames.
Each dataset is cached after the first load.

Add or rename datasets by updating DATASETS below.
Files are expected under the /data directory at project root.
"""

import os
import pandas as pd

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_cache: dict[str, pd.DataFrame] = {}

# Maps dataset name → Excel filename
DATASETS = {
    "sales":     "Sales",
    "hr":        "HR",
    "financial": "Financial_KPIs",
}


def get_dataset(name: str) -> pd.DataFrame:
    """Return a cached DataFrame for the given dataset name."""
    if name not in DATASETS:
        raise ValueError(f"Unknown dataset '{name}'. Available: {list(DATASETS)}")
    if name not in _cache:
        path = os.path.join(_DATA_DIR, "pernod_agent.xlsx")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Dataset file not found: {path}")
        _cache[name] = pd.read_excel(path)
    return _cache[name]


def get_schema() -> dict[str, list[str]]:
    """Return column names for all datasets."""
    return {name: list(get_dataset(name).columns) for name in DATASETS}


def get_schema_text() -> str:
    """Human-readable schema summary for use in prompts."""
    lines = []
    for name, columns in get_schema().items():
        lines.append(f"  {name}: {', '.join(columns)}")
    return "\n".join(lines)