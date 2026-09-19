#!/usr/bin/env python3
"""
Evaluation Runner for AI Support Ticket Decision System.
Reads test tickets from data/tickets.csv, runs the RAG + Decision pipeline,
and computes evaluation metrics.
"""

import sys
import csv
import argparse
from pathlib import Path
from src.retrieval import PolicyRAG
from src.decision import generate_decision, evaluate_policy_grounded


def run_evaluation(csv_path: Path, verbose: bool = False, use_llm: bool = False) -> float:
    if not csv_path.exists():
        print(f"Error: Evaluation file not found at {csv_path}", file=sys.stderr)
        sys.exit(1)

    rag = PolicyRAG()
    total = 0
    correct = 0
    incorrect = 0
    results = []

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            case_id = row.get("ticket_id") or row.get("id", str(total))
            message = row.get("message", "").strip()
            expected_action = (row.get("resolved_action") or row.get("expected_action", "")).strip().upper()

            chunks = rag.retrieve(message, top_k=3)
            if use_llm:
                decision = generate_decision(message, chunks, meta=row)
            else:
                decision = evaluate_policy_grounded(message, chunks, meta=row)

            pred_action = decision.action.strip().upper()
            is_correct = (pred_action == expected_action)
            if is_correct:
                correct += 1
            else:
                incorrect += 1

            results.append({
                "id": case_id,
                "message": message,
                "expected": expected_action,
                "predicted": pred_action,
                "confidence": decision.confidence,
                "correct": is_correct,
                "reason": decision.reason,
                "sources": decision.sources
            })

    accuracy = (correct / total * 100.0) if total > 0 else 0.0

    if verbose:
        print("\n" + "=" * 90)
        print(f"{'ID':<6} | {'STATUS':<6} | {'EXPECTED':<28} | {'PREDICTED':<28} | {'CONF':<4}")
        print("-" * 90)
        for r in results:
            status_str = "PASS" if r["correct"] else "FAIL"
            print(f"{r['id']:<6} | {status_str:<6} | {r['expected']:<28} | {r['predicted']:<28} | {r['confidence']:<4}")
        print("=" * 90 + "\n")

    # Required output format
    print(f"{total} test cases")
    print(f"Correct: {correct}")
    print(f"Incorrect: {incorrect}")
    print(f"Accuracy: {accuracy:.0f}%")

    return accuracy


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate AI Decision System against test dataset")
    parser.add_argument(
        "--file",
        type=str,
        default=str(Path(__file__).parent / "data" / "tickets.csv"),
        help="Path to evaluation CSV"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print per-case breakdown"
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Call Gemini LLM for each test case instead of grounded policy evaluator"
    )
    args = parser.parse_args()

    acc = run_evaluation(Path(args.file), verbose=args.verbose, use_llm=args.use_llm)
    if acc < 80.0:
        sys.exit(1)
