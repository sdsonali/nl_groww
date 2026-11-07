"""Golden set and agreement report.

The labelling file does not include the model's tags, so the PM can label first.

    python 5_evaluate.py
    python 5_evaluate.py --audit
"""

import argparse
import importlib.util

import pandas as pd

import config

AUDIT_PER_GROUP = 15
AUDIT_SAMPLE = config.DATA_DIR / "audit_sample.csv"
AUDIT_ANSWERS = config.DATA_DIR / "audit_answers.csv"
AUDIT_SAMPLE_COLUMNS = [
    "id",
    "source",
    "app",
    "text",
    "human_tree_node",
    "human_correct (yes/no)",
    "note",
]
AUDIT_ANSWER_COLUMNS = ["id", "group", "tree_node", "metric_scope", "action_taken"]

HUMAN_FIELDS = {
    "is_relevant": "human_is_relevant",
    "tree_node": "human_tree_node",
    "leak_type": "human_leak_type",
    "action_taken": "human_action_taken",
}
CORRECTION_COLUMNS = [
    "row_id",
    "text",
    "ai_output",
    "human_correction",
    "reason",
    "prompt_change",
]
TARGETS = {"is_relevant": 0.85, "tree_node": 0.75}


def _normalize(field, value):
    text = str(value).strip().lower()
    if text in {"", "nan", "none"}:
        return ""
    if field == "is_relevant":
        if text in {"true", "yes", "1", "relevant"}:
            return "true"
        if text in {"false", "no", "0", "not relevant", "irrelevant"}:
            return "false"
    return text


def write_golden(df):
    pool = df[df.get("status", "").astype(str).str.lower() == "ok"] if "status" in df.columns else df
    if len(pool) < 20:
        pool = df
    if pool.empty:
        print("No rows to sample.")
        return

    reserved_parts = []
    for _, group in pool.groupby("source"):
        reserved_parts.append(group.sample(1, random_state=24))
    reserved = pd.concat(reserved_parts, ignore_index=True)
    rest = pool[~pool["id"].isin(reserved["id"])]
    extra_parts = []
    if len(rest) and "journey_stage" in rest.columns:
        for _, group in rest.groupby("journey_stage"):
            extra_parts.append(group.sample(1, random_state=24))
    extra = pd.concat(extra_parts, ignore_index=True) if extra_parts else pool.head(0)
    picked = pd.concat([reserved, extra], ignore_index=True).drop_duplicates("id")
    if len(picked) < 20:
        more = pool[~pool["id"].isin(picked["id"])]
        need = min(24, len(pool)) - len(picked)
        if need > 0 and len(more):
            picked = pd.concat(
                [picked, more.sample(min(need, len(more)), random_state=24)],
                ignore_index=True,
            )
    if len(picked) > 25:
        keep_ids = set(reserved["id"])
        filler = picked[~picked["id"].isin(keep_ids)]
        room = 25 - len(keep_ids)
        if room > 0 and len(filler):
            filler = filler.sample(min(room, len(filler)), random_state=24)
            picked = pd.concat([reserved, filler], ignore_index=True)
        else:
            picked = reserved.head(25)

    out = picked[["id", "source", "app", "text"]].copy()
    for column in HUMAN_FIELDS.values():
        out[column] = ""
    config.write_csv(out, config.GOLDEN_CSV)
    print(f"Wrote {len(out)} rows to {config.GOLDEN_CSV.name}")
    print("Label the human_ columns before looking at the model tags in final.csv.")


def ensure_corrections():
    if config.CORRECTIONS_CSV.exists():
        return
    config.write_csv(pd.DataFrame(columns=CORRECTION_COLUMNS), config.CORRECTIONS_CSV)


def print_funnel():
    funnel = config.load_funnel()
    print("\nFunnel")
    if not funnel:
        print("No funnel file yet.")
        return
    for key in (
        "raw_total",
        "raw_by_source",
        "after_hygiene",
        "after_keyword_match",
        "after_keyword_cap",
        "after_relevance",
        "after_tag",
        "final",
        "final_ok",
        "needs_review",
    ):
        if key in funnel:
            print(f"  {key}: {funnel[key]}")


def evaluate(final):
    golden = config.read_csv(config.GOLDEN_CSV)
    if golden.empty:
        print("Golden file is empty.")
        return
    labelled = golden.copy()
    any_label = False
    for column in HUMAN_FIELDS.values():
        if column not in labelled.columns:
            labelled[column] = ""
        filled = labelled[column].astype(str).str.strip() != ""
        any_label = any_label or bool(filled.any())
    if not any_label:
        print("\nGolden file is ready. Human columns are still empty, so there is no agreement score yet.")
        print("Fill them in data/golden.csv, then run this script again.")
        return

    ai_cols = final[["id", "is_relevant", "tree_node", "leak_type", "action_taken"]]
    merged = labelled.merge(ai_cols, on="id", how="left")
    print("\nAgreement")
    disagreements = []
    for ai_field, human_field in HUMAN_FIELDS.items():
        compared = 0
        agreed = 0
        for _, row in merged.iterrows():
            human = _normalize(ai_field, row.get(human_field, ""))
            if not human:
                continue
            ai = _normalize(ai_field, row.get(ai_field, ""))
            compared += 1
            if human == ai:
                agreed += 1
            else:
                disagreements.append(
                    {
                        "id": row["id"],
                        "field": ai_field,
                        "ai": ai,
                        "human": human,
                        "text": str(row.get("text", ""))[:140],
                    }
                )
        rate = agreed / compared if compared else 0
        target = TARGETS.get(ai_field)
        line = f"  {ai_field}: {agreed}/{compared} ({rate:.0%})"
        if target is not None:
            line += f" — target {target:.0%}"
            if compared and rate < target:
                line += ". Below target. Adjust the prompt or HF_MODEL and record the attempt."
        print(line)
    if disagreements:
        print("\nDisagreements")
        print(pd.DataFrame(disagreements).to_string(index=False))
    else:
        print("\nNo disagreements on the labelled fields.")


def _score_module():
    spec = importlib.util.spec_from_file_location("score_mod", config.ROOT / "4_score.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _has_human_labels(frame):
    for column in ("human_tree_node", "human_correct (yes/no)", "note"):
        if column not in frame.columns:
            continue
        filled = frame[column].astype(str).str.strip()
        if filled.replace("nan", "").ne("").any():
            return True
    return False


def write_audit_sample(df):
    """15 comments from each audit group. Model tags go in a second file. Human columns stay empty."""
    if AUDIT_SAMPLE.exists():
        existing = config.read_csv(AUDIT_SAMPLE)
        if _has_human_labels(existing):
            print("audit_sample.csv already has human labels. It was not overwritten.")
            return
    score = _score_module()
    ok = score.usable(df)
    actions = score._actions(ok)
    stop = ok[actions.isin(score.STOP_ACTIONS) | ok["tree_node"].astype(str).eq("C1")]
    node_pool = ok
    if "metric_scope" in ok.columns:
        node_pool = ok[ok["metric_scope"].astype(str).eq("in_scope")].copy()
    labels, _also = score.reason_assignment(stop)
    named = labels[labels.astype(str).ne("") & labels.astype(str).ne("No matching reason")]
    top_reasons = list(named.value_counts().head(3).index)
    used = set()
    sample_rows = []
    answer_rows = []

    def take(pool, group):
        pool = pool[~pool["id"].astype(str).isin(used)]
        n = min(AUDIT_PER_GROUP, len(pool))
        print(f"  {group}: {n} of {len(pool)} available (cap {AUDIT_PER_GROUP})")
        if n == 0:
            return
        picked = pool.sample(n, random_state=15)
        used.update(picked["id"].astype(str))
        for _, row in picked.iterrows():
            sample_rows.append(
                {
                    "id": row.get("id", ""),
                    "source": row.get("source", ""),
                    "app": row.get("app", ""),
                    "text": row.get("text", ""),
                    "human_tree_node": "",
                    "human_correct (yes/no)": "",
                    "note": "",
                }
            )
            answer_rows.append(
                {
                    "id": row.get("id", ""),
                    "group": group,
                    "tree_node": row.get("tree_node", ""),
                    "metric_scope": row.get("metric_scope", ""),
                    "action_taken": row.get("action_taken", ""),
                }
            )

    print("Audit groups")
    for reason in top_reasons:
        take(stop.loc[labels[labels == reason].index], reason)
    for node in ("C2", "A1", "C1", "none"):
        take(node_pool[node_pool["tree_node"].astype(str).eq(node)], node)
    sample = pd.DataFrame(sample_rows, columns=AUDIT_SAMPLE_COLUMNS)
    answers = pd.DataFrame(answer_rows, columns=AUDIT_ANSWER_COLUMNS)
    config.assert_no_identifiers(sample)
    config.write_csv(sample, AUDIT_SAMPLE)
    config.write_csv(answers, AUDIT_ANSWERS)
    print(f"Wrote {len(sample)} rows to {AUDIT_SAMPLE.name}")
    print(f"Model tags are in {AUDIT_ANSWERS.name}. Human columns were left empty.")


STAGE_OF = {
    "A": "A",
    "A1": "A",
    "A2": "A",
    "B": "B",
    "B1": "B",
    "B2": "B",
    "C": "C",
    "C1": "C",
    "C2": "C",
    "C3": "C",
    "D1": "C",
    "E1": "C",
    "none": "none",
}


def stage_of(node):
    """Map a tree node to A, B, C, or none. D1 and E1 count as C."""
    raw = str(node or "").strip()
    if not raw or raw.lower() in {"nan"}:
        return ""
    key = "none" if raw.lower() == "none" else raw.upper()
    return STAGE_OF.get(key, "")


def pipeline_node(tree_node, metric_scope):
    """The pipeline keeps a node only for an in-scope comment. Every other scope is none."""
    if str(metric_scope or "").strip() != "in_scope":
        return "none"
    raw = str(tree_node or "").strip()
    return "none" if raw.lower() == "none" else raw.upper() if raw else "none"


def _agreement_counts(frame, predicted_node):
    """Stage, exact node, none, and stage C against the human labels."""
    stage_hit = exact_hit = 0
    none_hit = none_n = c_hit = c_n = 0
    for _, row in frame.iterrows():
        human = str(row.get("human_tree_node", "") or "").strip()
        predicted = predicted_node(row)
        human_stage = stage_of(human)
        predicted_stage = stage_of(predicted)
        if human_stage and human_stage == predicted_stage:
            stage_hit += 1
        if human.lower() == str(predicted).strip().lower():
            exact_hit += 1
        if human_stage == "none":
            none_n += 1
            none_hit += int(predicted_stage == "none")
        if human_stage == "C":
            c_n += 1
            c_hit += int(predicted_stage == "C")
    return {
        "n": len(frame),
        "stage": stage_hit,
        "exact": exact_hit,
        "none": none_hit,
        "none_n": none_n,
        "c": c_hit,
        "c_n": c_n,
    }


def _print_counts(title, counts):
    print(title)
    print(f"  stage agreement: {counts['stage']} of {counts['n']}")
    print(f"  exact-node agreement: {counts['exact']} of {counts['n']}")
    print(f"  agreement on none: {counts['none']} of {counts['none_n']}")
    print(f"  agreement on stage C: {counts['c']} of {counts['c_n']}")


def print_model_and_pipeline(frame, heading="Current saved tags"):
    """Print the raw model tables and the pipeline tables. The pipeline is what the product uses."""
    print(f"\n{heading}")
    _print_counts(
        "Model tree_node, before the scope gate",
        _agreement_counts(frame, lambda row: row.get("tree_node", "")),
    )
    _print_counts(
        "Pipeline stage. This is the pipeline's real output: the model stage is kept only when metric_scope is in_scope. Otherwise the output is none.",
        _agreement_counts(frame, lambda row: pipeline_node(row.get("tree_node", ""), row.get("metric_scope", ""))),
    )


def compare_audit():
    """Score the audit after the PM has filled human_correct. An empty sheet prints zeros."""
    sample = config.read_csv(AUDIT_SAMPLE)
    answers = config.read_csv(AUDIT_ANSWERS)
    if sample.empty or answers.empty:
        print("Audit files are missing or empty.")
        return
    merged = sample.merge(answers, on="id", how="left")
    correct_col = "human_correct (yes/no)"
    if correct_col not in merged.columns:
        print(f"Column {correct_col} is missing.")
        return
    marked = merged[correct_col].astype(str).str.strip().str.lower()
    labelled = merged[marked.isin(["yes", "no"])].copy()
    print(f"Labelled {len(labelled)} of {len(merged)}.")
    groups = merged["group"] if "group" in merged.columns else pd.Series(["all"] * len(merged))
    if labelled.empty:
        print("No human labels yet. Fill human_correct (yes/no) in data/audit_sample.csv, then run this again.")
        for group, part in merged.groupby(groups):
            print(f"  {group}: 0 of {len(part)} labelled")
        return
    disagreements = []
    labelled_mark = labelled[correct_col].astype(str).str.strip().str.lower()
    for group, part in labelled.groupby(labelled["group"] if "group" in labelled.columns else groups.loc[labelled.index]):
        yes = int(labelled_mark.loc[part.index].eq("yes").sum())
        print(f"  {group}: {yes} of {len(part)} correct")
        wrong = part[labelled_mark.loc[part.index].eq("no")]
        for _, row in wrong.iterrows():
            disagreements.append(
                {
                    "group": group,
                    "id": row.get("id", ""),
                    "model_tree_node": row.get("tree_node", ""),
                    "human_tree_node": row.get("human_tree_node", ""),
                    "text": str(row.get("text", ""))[:140],
                }
            )
    if disagreements:
        print("\nDisagreements")
        print(pd.DataFrame(disagreements).to_string(index=False))
    else:
        print("\nNo disagreements on the labelled rows.")
    print_model_and_pipeline(merged)


def main():
    parser = argparse.ArgumentParser(description="Golden set and audit sample")
    parser.add_argument("--audit", action="store_true", help="Write the audit sample and compare any human labels")
    args = parser.parse_args()
    config.ensure_data_dir()
    if args.audit:
        final = config.read_csv(config.FINAL_CSV)
        if final.empty:
            print("No final.csv yet. Run 3_filter_tag.py first.")
            return
        write_audit_sample(final)
        compare_audit()
        return
    ensure_corrections()
    final = config.read_csv(config.FINAL_CSV)
    if final.empty:
        print("No final.csv yet. Run 3_filter_tag.py first.")
        return
    config.assert_no_identifiers(final)
    if not config.GOLDEN_CSV.exists():
        write_golden(final)
    else:
        print(f"{config.GOLDEN_CSV.name} already exists. It was not overwritten.")
    evaluate(final)
    print_funnel()
    corrections = config.read_csv(config.CORRECTIONS_CSV)
    print("\nCorrection log")
    if corrections.empty:
        print("No corrections recorded yet. Add 2 or 3 rows to data/corrections.csv after review.")
        print("Columns: " + ", ".join(CORRECTION_COLUMNS))
    else:
        print(corrections.to_string(index=False))
    print("\nPrivacy: public text only. No usernames, profile links, or other personal identifiers are stored.")
    print(config.NOT_ADVICE)


if __name__ == "__main__":
    main()
