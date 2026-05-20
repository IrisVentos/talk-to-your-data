"""
visualizer.py
-------------
Simple chart generation from query results.
Uses matplotlib to create and display/save charts based on the data.
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")  
import matplotlib.pyplot as plt


def detect_chart_request(question: str) -> bool:
    """Check if the user is asking for a visualization."""
    chart_keywords = [
        "chart", "graph", "plot", "visuali", "bar chart", "line chart",
        "pie chart", "histogram", "trend", "draw", "show me a graph",
        "build a chart", "create a chart", "display a chart",
    ]
    q = question.lower()
    return any(kw in q for kw in chart_keywords)


def infer_chart_type(df: pd.DataFrame, question: str) -> str:
    """Infer the best chart type from the data shape and user request."""
    q = question.lower()
    if "pie" in q:
        return "pie"
    if "line" in q or "trend" in q or "over time" in q or "over the year" in q:
        return "line"
    if "histogram" in q or "distribution" in q:
        return "hist"
    # Auto-detect: if first column looks like time periods, use line
    if len(df.columns) >= 2:
        first_col = df.columns[0]
        if any(kw in first_col.lower() for kw in ["month", "quarter", "year", "period", "date"]):
            return "line"
    return "bar"


def generate_chart(df: pd.DataFrame, question: str, intent: str = "") -> str:
    """
    Generate a chart from DataFrame and return the file path.
    Returns the path to the saved PNG image.
    """
    chart_type = infer_chart_type(df, question)

    fig, ax = plt.subplots(figsize=(10, 6))

    # Use first column as x-axis, remaining numeric columns as y-axis
    if len(df.columns) < 2:
        ax.bar(range(len(df)), df.iloc[:, 0])
        ax.set_ylabel(df.columns[0])
    else:
        x_col = df.columns[0]
        # Get numeric columns for y-axis
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if not numeric_cols:
            numeric_cols = [df.columns[1]]

        x_values = df[x_col].astype(str)

        if chart_type == "line":
            for col in numeric_cols:
                ax.plot(x_values, df[col], marker="o", label=col)
            if len(numeric_cols) > 1:
                ax.legend()
        elif chart_type == "bar":
            if len(numeric_cols) == 1:
                ax.bar(x_values, df[numeric_cols[0]], color="steelblue")
                ax.set_ylabel(numeric_cols[0])
            else:
                width = 0.8 / len(numeric_cols)
                for i, col in enumerate(numeric_cols):
                    positions = [x + i * width for x in range(len(df))]
                    ax.bar(positions, df[col], width=width, label=col)
                ax.set_xticks([x + width * (len(numeric_cols) - 1) / 2 for x in range(len(df))])
                ax.set_xticklabels(x_values)
                ax.legend()
        elif chart_type == "pie":
            values = df[numeric_cols[0]]
            ax.pie(values, labels=x_values, autopct="%1.1f%%", startangle=90)
            ax.set_ylabel("")
        elif chart_type == "hist":
            ax.hist(df[numeric_cols[0]], bins=min(20, len(df)), color="steelblue", edgecolor="white")
            ax.set_xlabel(numeric_cols[0])
            ax.set_ylabel("Frequency")

    # Title and formatting
    title = intent if intent else question[:60]
    ax.set_title(title, fontsize=12, fontweight="bold")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    # Save to charts/ folder
    output_dir = os.path.join(os.path.dirname(__file__), "..", "charts")
    os.makedirs(output_dir, exist_ok=True)

    safe_name = "".join(c if c.isalnum() or c in " _-" else "" for c in title)[:40].strip()
    filepath = os.path.join(output_dir, f"{safe_name}.png")

    fig.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return os.path.abspath(filepath)
