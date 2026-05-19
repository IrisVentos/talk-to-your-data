"""
main.py
-------
Minimal CLI to run the FMCG data agent interactively.

Usage:
    python main.py                        # reads ANTHROPIC_API_KEY from env / .env
    ANTHROPIC_API_KEY=sk-ant-... python main.py
"""

import os
import anthropic
import httpx  
from dotenv import load_dotenv

from agent import run, save_query

load_dotenv()


def _print_result(result) -> None:
    print()
    if result.is_out_of_scope:
        print(f"[out of scope] {result.answer}")
        return

    tag = f"[query {result.query_id}]" if result.query_id else "[new query]"
    print(f"{tag} {result.answer}")

    if result.table:
        print(f"  → {len(result.table)} row(s) returned")

    if result.proposed_query:
        q = result.proposed_query
        print(f"\n  ⚠  New query proposed: '{q['intent']}' on dataset '{q['dataset']}'")
        print(f"     Code: {q['pandas_code']}")
        ans = input("  Validate and save? (y/n): ").strip().lower()
        if ans == "y":
            new_id = save_query(q)
            print(f"  ✓ Saved as {new_id}")
        else:
            print("  Discarded.")


def main() -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY not set. Add it to .env or your environment.")

    client = anthropic.Anthropic(
        api_key=api_key,
        http_client=httpx.Client(verify=False)
    )

    print("FMCG Data Agent — type 'exit' to quit.")
    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in ("exit", "quit", "q"):
            break
        if not question:
            continue
        result = run(question, client)
        _print_result(result)


if __name__ == "__main__":
    main()