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
from src.decision import generate_decision


def run_evaluation(csv_path: Path, verbose: bool = False) -> float:
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
            case_id = row.get("id", str(total))
            message = row.get("message", "").strip()
            expected_action = row.get("expected_action", "").strip().upper()
            expected_source = row.get("expected_source", "").strip()

            chunks = rag.retrieve(message, top_k=3)
            decision = generate_decision(message, chunks)
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
        print("\n" + "=" * 80)
        print(f"{'ID':<4} | {'STATUS':<7} | {'EXPECTED':<22} | {'PREDICTED':<22} | {'CONF':<4}")
        print("-" * 80)
        for r in results:
            status_str = "PASS" if r["correct"] else "FAIL"
            print(f"{r['id']:<4} | {status_str:<7} | {r['expected']:<22} | {r['predicted']:<22} | {r['confidence']:<4}")
        print("=" * 80 + "\n")

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
    args = parser.parse_args()

    acc = run_evaluation(Path(args.file), verbose=args.verbose)
    if acc < 80.0:
        sys.exit(1)
