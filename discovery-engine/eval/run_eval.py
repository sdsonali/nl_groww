"""Run the chat pipeline on the golden file. No message text is written."""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chat.pipeline import run_turn  # noqa: E402

EVAL = Path(__file__).resolve().parent
GOLDEN = EVAL / "golden.csv"
RESULTS = EVAL / "results.csv"
SUMMARY = EVAL / "summary.json"


def load_rows():
    with GOLDEN.open(newline="") as handle:
        return list(csv.DictReader(handle))


def labelled(rows):
    ready = []
    for row in rows:
        if (row.get("expected_action") or "").strip() and (row.get("expected_agent") or "").strip():
            ready.append(row)
    return ready


def is_test_row(index):
    """Even positions are the test set. Index 0 is the first row."""
    return index % 2 == 1


def run(rows):
    results = []
    for index, row in enumerate(rows):
        context = {
            "screen": "instalment_recovery",
            "scenario": row.get("scenario") or "",
            "autopay_state": "",
            "sip_amount": 2000,
            "debit_day": 5,
            "values": "sample",
        }
        outcome = run_turn(row.get("question") or "", context)
        action = outcome.get("action") or ""
        agent = outcome.get("agent") or ""
        ids = outcome.get("kb_ids") or []
        expected_action = (row.get("expected_action") or "").strip()
        expected_agent = (row.get("expected_agent") or "").strip()
        expected_kb = (row.get("expected_kb_id") or "").strip()
        route_ok = agent == expected_agent
        action_ok = action == expected_action
        grounded = (not expected_kb) or (expected_kb in ids)
        if action != "answer":
            grounded = action_ok
        reason = ""
        if not action_ok:
            reason = "action " + action + " expected " + expected_action
        elif not route_ok:
            reason = "agent " + agent + " expected " + expected_agent
        elif action == "answer" and expected_kb and expected_kb not in ids:
            reason = "kb id missing"
        results.append(
            {
                "id": row.get("id"),
                "split": "test" if is_test_row(index) else "tune",
                "language": row.get("language") or "",
                "expected_action": expected_action,
                "action": action,
                "expected_agent": expected_agent,
                "agent": agent,
                "expected_kb_id": expected_kb,
                "kb_ids": "|".join(ids),
                "route_ok": route_ok,
                "action_ok": action_ok,
                "grounded": grounded,
                "reason": reason,
            }
        )
    return results


def _rate(rows, predicate):
    if not rows:
        return None
    return round(sum(1 for row in rows if predicate(row)) / len(rows), 4)


def summarize(results, unlabelled):
    declines = [row for row in results if row["expected_action"] == "decline"]
    missed = [row for row in declines if row["action"] != "decline"]
    answerable = [row for row in results if row["expected_action"] == "answer"]
    false_declines = [row for row in answerable if row["action"] == "decline"]
    answered = [row for row in results if row["action"] == "answer" and row["expected_action"] == "answer"]
    hinglish = [row for row in results if row["language"] == "hinglish"]
    failed = [row for row in results if row["reason"]]
    return {
        "status": "scored",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tested_on": len(results),
        "unlabelled_rows": unlabelled,
        "note": "Even rows are the test set and were scored once. Odd rows are the tune set and are not in these numbers.",
        "metrics": {
            "routing_accuracy": _rate(results, lambda row: row["route_ok"]),
            "action_accuracy": _rate(results, lambda row: row["action_ok"]),
            "advice_decline_recall": _rate(declines, lambda row: row["action"] == "decline"),
            "false_decline_rate": _rate(answerable, lambda row: row["action"] == "decline"),
            "grounding": _rate(answered, lambda row: row["grounded"]) if answered else None,
            "hinglish_action_accuracy": _rate(hinglish, lambda row: row["action_ok"]),
        },
        "advice_decline_misses": [row["id"] for row in missed],
        "false_declines": [row["id"] for row in false_declines],
        "failed_rows": [{"id": row["id"], "reason": row["reason"]} for row in failed],
    }


def write_outputs(results, summary):
    fields = list(results[0].keys()) if results else ["id"]
    with RESULTS.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    SUMMARY.write_text(json.dumps(summary, indent=2))


def main():
    rows = load_rows()
    ready = labelled(rows)
    test_rows = []
    for index, row in enumerate(rows):
        if not is_test_row(index):
            continue
        if (row.get("expected_action") or "").strip() and (row.get("expected_agent") or "").strip():
            test_rows.append(row)
    unlabelled = len(rows) - len(ready)
    if not test_rows:
        summary = {
            "status": "not_run",
            "date": None,
            "tested_on": 0,
            "unlabelled_rows": unlabelled,
            "note": "No labelled even rows yet. Fill expected_agent and expected_action in eval/golden.csv.",
            "metrics": {},
            "advice_decline_misses": [],
            "false_declines": [],
            "failed_rows": [],
        }
        SUMMARY.write_text(json.dumps(summary, indent=2))
        print(summary["note"])
        return
        results = run(test_rows)
        for row in results:
            row["split"] = "test"
    summary = summarize(results, unlabelled)
    write_outputs(results, summary)
    print(json.dumps(summary["metrics"], indent=2))
    print("Failed rows:", len(summary["failed_rows"]))


if __name__ == "__main__":
    main()
