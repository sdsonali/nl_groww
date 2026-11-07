"""Opportunity scores for the SIP metric tree.

Opportunity = frequency x severity x fixability.
Fixability comes from config.py. This script does not ask a model to set it.
Severity comes from sip_outcome when that field is present.

    python 4_score.py
"""

import csv
import re
from datetime import date

import pandas as pd

import config

OUTCOME_SEVERITY = {
    "ended": 3,
    "paused_or_reduced": 2,
    "continuing": 1,
    "unclear": 1,
}
SEVERITY_SENTENCE = (
    "Severity is 3 when the SIP stopped and did not restart, "
    "2 when it was paused, reduced, or the person is considering stopping, "
    "and 1 when they are confused or complaining but still continuing, "
    "including a failed debit that the comment does not say ended the SIP."
)

STOP_ACTIONS = {"paused", "cancelled", "reduced"}
KEEP_ACTIONS = {"continued", "restarted"}
BLANK_VALUES = {"", "none", "null", "unclear", "not available"}
STAGE_LABELS = {
    "start": "Starting",
    "settle_in_m1_3": "Months 1–3",
    "middle_m4_9": "Months 4–9",
    "month_12_plus": "Around month 12",
    "restart": "Restart",
    "unclear": "Stage unclear",
}
CHECK_WORD = re.compile(
    r"\b(check|checking|checked|dekht[ae]|dekhu|open(?:ed)? the app|log ?in|portfolio|statement)\b",
    re.I,
)
CHECK_RHYTHM = [
    ("daily", re.compile(r"\b(every day|everyday|daily|roz|har din)\b", re.I)),
    ("weekly", re.compile(r"\b(every week|weekly|har hafte)\b", re.I)),
    ("when the value moves", re.compile(r"\b(market gir|nav gir|when (the )?(market|nav)|jab (market|nav))\b", re.I)),
]
# Reasons are read from the comment text. The trigger field often just repeats "cancel SIP".
START_THEMES = [
    ("They want a monthly investing habit", re.compile(r"every month|monthly|har mahine|discipline|regular", re.I)),
    ("They want to start with a small amount", re.compile(r"\b500\b|\b100\b|small amount|kam amount", re.I)),
    ("Someone else suggested it", re.compile(r"friend|youtube|family|suggested|recommended", re.I)),
    ("They are thinking long term", re.compile(r"long term|retirement|future", re.I)),
    ("Tax saving, often an ELSS fund", re.compile(r"\btax\b|80c|\belss\b", re.I)),
]
# Hard to withdraw: the comment must say money was delayed or could not be taken out.
# A bare "redeem" or "withdraw" is not enough. Both a money-out word and a delay word are required.
MONEY_OUT = re.compile(
    r"withdraw|redemption|\bredeem\b|refund|payout|nikal|paise|paisa",
    re.I,
)
MONEY_DELAY = re.compile(
    r"not received|never received|haven'?t received|not credited|"
    r"\bpending\b|\bstuck\b|\bprocessing\b|still waiting|"
    r"\bdelay(?:ed)?\b|taking (?:longer|too long)|"
    r"nahi (?:aaya|aaye|aya|aye|mila|mile|hua|hue|ho)|"
    r"nhi (?:aaya|aaye|aya|aye|mila|mile|hua|hue)|"
    r"atka|atke|atak|phas gaya|"
    r"can'?t withdraw|cannot withdraw|unable to withdraw|not able to withdraw|"
    r"could not withdraw|withdraw nahi|redeem(?:ption)? nahi|nikal nahi",
    re.I,
)
SIP_WORD = re.compile(r"\bsips?\b|systematic investment", re.I)
SIP_STOP = re.compile(
    r"\b(?:cancel(?:led|ed|ing)?|stopped|stop(?:ping)?|discontinu(?:ed|ing)?|quit)\b|band kar|band kiya|rok diya",
    re.I,
)
NON_SIP_CANCEL = re.compile(
    r"(?:cancel(?:led|ed|ing)?|clos(?:e|ed|ing)|delet(?:e|ed|ing)|deactivat\w*|uninstall(?:ed|ing)?)"
    r".{0,40}"
    r"(?:account|subscription|prime plan|paid plan|\bgenius\b|membership|the app)"
    r"|(?:account|subscription|prime plan|paid plan|genius membership)"
    r".{0,40}"
    r"(?:cancel(?:led|ed|ing)?|clos(?:e|ed)|delet(?:e|ed)|uninstall)",
    re.I,
)
CANCELLED_NO_REASON = "Cancelled, no reason given"
NOT_A_SIP_CANCEL = "Cancelled an account, plan, or app, not a SIP"


class PhraseRule:
    """Matches only when a money-out word and a delay or non-receipt word are both present."""

    def __init__(self):
        self.pattern = MONEY_DELAY.pattern

    def search(self, text):
        if not text:
            return None
        if MONEY_OUT.search(text) and MONEY_DELAY.search(text):
            return True
        return None


WITHDRAW_DIFFICULTY = PhraseRule()
REASON_THEMES = [
    ("Money was hard to withdraw, or redemption was slow", WITHDRAW_DIFFICULTY),
    ("Support did not resolve it", re.compile(r"support|customer service|customer care|no response|no reply|\bticket\b", re.I)),
    ("The market fell or the value looked down", re.compile(r"market (?:gir|fall|down|crash)|gir gaya|\bloss\b|negative return|volatile", re.I)),
    ("They lost trust, often after a paid plan", re.compile(r"\btrust\b|prime plan|\bgenius\b|subscription", re.I)),
    ("A bank charge or a bounce fee", re.compile(r"\bcharges?\b|\bnach\b|bounce fee|penalty", re.I)),
    ("A lock-in, often an ELSS fund", re.compile(r"\belss\b|lock-?in", re.I)),
    ("The app showed a wrong amount or blocked a step", re.compile(r"wrong (?:amount|value)|otp|\bxirr\b", re.I)),
    ("They needed the cash for an expense", re.compile(r"expense|hospital|operation|emergency", re.I)),
    ("Autopay or a mandate was forced or failed", re.compile(r"autopay|auto[- ]?pay|\bmandate\b|e-?nach", re.I)),
]
JUNK_REASON = re.compile(
    r"short phrase or null|one line in the user|exact substring|user's own words",
    re.I,
)
LATER_STAGES = {"settle_in_m1_3", "middle_m4_9", "month_12_plus"}


FUND_PATTERN = re.compile(
    r"(?i)\b(?:quant|hdfc|sbi|axis|icici(?:\s+prudential)?|nippon(?:\s+india)?|mirae(?:\s+asset)?|"
    r"parag\s+parikh|ppfas|motilal(?:\s+oswal)?|kotak|uti|tata|bandhan|dsp|franklin|"
    r"edelweiss|canara\s+robeco|aditya\s+birla|birla|pgim|invesco|white\s*oak|navi)\b"
    r"(?:\s+[A-Za-z][\w\-']*){0,4}"
)
TOO_FEW = "Too few comments to rely on"


def mask_fund_names(text):
    """Replace a fund or scheme name in text that will be shown. Does not change stored comments."""
    original = "" if text is None else str(text)
    updated = original
    for term in sorted(config.BLOCK_TERMS, key=len, reverse=True):
        updated = re.sub(re.escape(term), "[fund name]", updated, flags=re.I)
    updated = FUND_PATTERN.sub("[fund name]", updated)
    updated = re.sub(r"(?:\[fund name\]\s*){2,}", "[fund name] ", updated).strip()
    return updated, updated != original


def usable(df):
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    work["confidence"] = pd.to_numeric(work.get("confidence", 0), errors="coerce").fillna(0)
    relevant = work.get("is_relevant", "").astype(str).str.lower().isin(["true", "1", "yes"])
    ok = work.get("status", "").astype(str).str.lower().eq("ok")
    return work[relevant & ok].copy()


def _one_severity(row):
    outcome = str(row.get("sip_outcome", "") or "").strip()
    if outcome in OUTCOME_SEVERITY:
        return OUTCOME_SEVERITY[outcome]
    return config.SEVERITY.get(str(row.get("action_taken", "")), 1)


def _severity(part):
    if part is None or len(part) == 0:
        return 1.0
    scores = [_one_severity(row) for row in part.to_dict("records")]
    if not scores:
        return 1.0
    return sum(scores) / len(scores)


def _rows_for(frame, slice_type, slice_value, total):
    rows = []
    if total <= 0:
        return rows
    for node, label in config.TREE.items():
        part = frame[frame["tree_node"] == node]
        n = len(part)
        if n == 0:
            continue
        frequency = n / total
        severity = _severity(part)
        fix = config.FIXABILITY.get(node, config.FIXABILITY["none"])
        voluntary = int((part.get("leak_type", "") == "voluntary").sum()) if n else 0
        involuntary = int((part.get("leak_type", "") == "involuntary").sum()) if n else 0
        small = n < 30
        rows.append(
            {
                "slice_type": slice_type,
                "slice_value": slice_value,
                "tree_node": node,
                "node_label": label,
                "n": n,
                "frequency": round(frequency, 4),
                "severity": round(severity, 2),
                "fixability": fix["score"],
                "fixability_reason": fix["reason"],
                "score": round(frequency * severity * fix["score"], 4),
                "voluntary_n": voluntary,
                "involuntary_n": involuntary,
                "small_sample": small,
                "note": config.SMALL_SAMPLE_NOTE if small else "",
            }
        )
    return rows


def version_scores(df):
    """Four score versions for nodes other than none. Frequency uses every confident row as the base."""
    ok = usable(df)
    total = len(ok)
    rows = []
    if total <= 0:
        return pd.DataFrame()
    for node in config.TREE:
        if node == "none":
            continue
        part = ok[ok["tree_node"].astype(str) == node]
        n = len(part)
        if n == 0:
            continue
        frequency = n / total
        severity = _severity(part)
        fix = config.FIXABILITY.get(node, config.FIXABILITY["none"])["score"]
        rows.append(
            {
                "tree_node": node,
                "n": n,
                "Frequency x Severity x Fixability": round(frequency * severity * fix, 4),
                "Frequency x Severity": round(frequency * severity, 4),
                "Frequency only": round(frequency, 4),
                "Frequency x Fixability": round(frequency * fix, 4),
            }
        )
    return pd.DataFrame(rows)


def top_versions(df, limit=5):
    table = version_scores(df)
    if table.empty:
        return table, {}
    tops = {}
    columns = [
        "Frequency x Severity x Fixability",
        "Frequency x Severity",
        "Frequency only",
        "Frequency x Fixability",
    ]
    for column in columns:
        ordered = table.sort_values([column, "n"], ascending=[False, False])
        tops[column] = ordered.iloc[0]["tree_node"]
    return table, tops


def build_ranking(df):
    ok = usable(df)
    rows = _rows_for(ok, "all", "all", len(ok))
    for column in ("income_type", "age_hint", "influenced_by"):
        if column not in ok.columns:
            continue
        for value, part in ok.groupby(column):
            if str(value).strip() == "":
                continue
            rows.extend(_rows_for(part, column, value, len(part)))
    ranking = pd.DataFrame(rows)
    if ranking.empty:
        return ranking
    return ranking.sort_values(["slice_type", "score"], ascending=[True, False])


def stage_split(df):
    ok = usable(df)
    rows = []
    if ok.empty or "journey_stage" not in ok.columns:
        return pd.DataFrame(rows)
    for stage, part in ok.groupby("journey_stage"):
        n = len(part)
        voluntary = int((part["leak_type"] == "voluntary").sum())
        involuntary = int((part["leak_type"] == "involuntary").sum())
        rows.append(
            {
                "journey_stage": stage,
                "n": n,
                "voluntary_n": voluntary,
                "involuntary_n": involuntary,
                "voluntary_share": round(voluntary / n, 3) if n else 0,
                "involuntary_share": round(involuntary / n, 3) if n else 0,
                "note": config.SMALL_SAMPLE_NOTE if n < 30 else "",
            }
        )
    return pd.DataFrame(rows).sort_values("n", ascending=False)


def top_counts(df, column, limit=8):
    ok = usable(df)
    if ok.empty or column not in ok.columns:
        return pd.DataFrame(columns=[column, "n"])
    series = ok[column].fillna("").astype(str).str.strip()
    series = series[~series.str.lower().isin({"", "none", "null", "unclear", "not available"})]
    counts = series.value_counts().head(limit).reset_index()
    counts.columns = [column, "n"]
    return counts


def quotes_by_node(df):
    ok = usable(df)
    found = {}
    if ok.empty:
        return found
    for node in config.TREE:
        part = ok[ok["tree_node"] == node]
        if "evidence_quote" not in part.columns:
            continue
        quotes = []
        ordered = part.sort_values("confidence", ascending=False)
        for quote in ordered["evidence_quote"].astype(str):
            words = quote.split()
            if quote and len(words) <= 15 and quote not in quotes:
                quotes.append(quote)
            if len(quotes) == 3:
                break
        if quotes:
            found[node] = quotes
    return found


def brand_of(row):
    if str(row.get("source")) == "youtube":
        return "YouTube"
    app = str(row.get("app") or "").strip()
    return app or "Other"


def brand_mix(df):
    ok = usable(df)
    if ok.empty:
        return pd.DataFrame()
    work = ok.copy()
    work["brand"] = work.apply(brand_of, axis=1)
    counts = work.groupby(["brand", "tree_node"]).size().reset_index(name="n")
    totals = work.groupby("brand").size().to_dict()
    counts["brand_n"] = counts["brand"].map(totals)
    counts["share_of_brand"] = (counts["n"] / counts["brand_n"]).round(3)
    counts["note"] = counts["brand_n"].map(lambda n: config.SMALL_SAMPLE_NOTE if n < 30 else "")
    return counts.sort_values(["brand", "n"], ascending=[True, False])


def _filled(series):
    text = series.fillna("").astype(str).str.strip()
    return text[~text.str.lower().isin(BLANK_VALUES)]


def _top(df, column, limit=6):
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=[column, "n"])
    counts = _filled(df[column]).value_counts().head(limit).reset_index()
    counts.columns = [column, "n"]
    return counts


def _quotes(df, limit=3):
    if df.empty or "evidence_quote" not in df.columns:
        return []
    ordered = df
    if "confidence" in df.columns:
        ordered = df.assign(_confidence=pd.to_numeric(df["confidence"], errors="coerce").fillna(0))
        ordered = ordered.sort_values("_confidence", ascending=False)
    quotes = []
    for quote in ordered["evidence_quote"].astype(str):
        quote = quote.strip()
        if quote.lower() in BLANK_VALUES or len(quote.split()) > 15 or quote in quotes:
            continue
        quotes.append(quote)
        if len(quotes) == limit:
            break
    return quotes


def _comments(n):
    n = int(n)
    return "1 comment" if n == 1 else f"{n} comments"


def _verb(n, one, many):
    return one if int(n) == 1 else many


def _slice_note(n, extra=""):
    parts = []
    if n < 30:
        parts.append(config.SMALL_SAMPLE_NOTE)
    if extra:
        parts.append(extra)
    return " ".join(parts)


def _actions(df):
    if df.empty or "action_taken" not in df.columns:
        return pd.Series(dtype=str)
    return df["action_taken"].fillna("").astype(str).str.strip()


def _behaviour_table(ok):
    rows = []
    for stage, label in STAGE_LABELS.items():
        part = ok[ok["journey_stage"].astype(str) == stage]
        if part.empty:
            continue
        actions = _actions(part)
        rows.append(
            {
                "stage": label,
                "n": len(part),
                "still_investing": int(actions.isin(KEEP_ACTIONS).sum()),
                "paused_reduced_or_stopped": int(actions.isin(STOP_ACTIONS).sum()),
                "failed_debit": int((actions == "failed_debit").sum()),
                "most_common_action": actions.value_counts().index[0] if len(actions) else "",
                "note": config.SMALL_SAMPLE_NOTE if len(part) < 30 else "",
            }
        )
    return pd.DataFrame(rows)


def _check_rhythm(ok):
    counts = {name: 0 for name, _pattern in CHECK_RHYTHM}
    named = 0
    if "text" not in ok.columns:
        return named, counts
    for text in ok["text"].fillna("").astype(str):
        if not CHECK_WORD.search(text):
            continue
        named += 1
        for name, pattern in CHECK_RHYTHM:
            if pattern.search(text):
                counts[name] += 1
                break
    return named, counts


def _segment_table(ok):
    rows = []
    cuts = [
        ("income_type", "Income stability"),
        ("age_hint", "Age hint"),
        ("influenced_by", "Who influenced them"),
    ]
    for column, label in cuts:
        if column not in ok.columns:
            continue
        values = ok[column].fillna("").astype(str).str.strip()
        for value, part in ok.groupby(values):
            if str(value).lower() in BLANK_VALUES:
                continue
            actions = _actions(part)
            rows.append(
                {
                    "segment": label,
                    "value": value,
                    "n": len(part),
                    "still_investing": int(actions.isin(KEEP_ACTIONS).sum()),
                    "paused_reduced_or_stopped": int(actions.isin(STOP_ACTIONS).sum()),
                    "note": config.SMALL_SAMPLE_NOTE if len(part) < 30 else "",
                }
            )
    if not rows:
        return pd.DataFrame(columns=["segment", "value", "n", "still_investing", "paused_reduced_or_stopped", "note"])
    return pd.DataFrame(rows).sort_values(["segment", "n"], ascending=[True, False])


def _block(question, lead, tables=None, quotes=None, note=""):
    return {
        "question": question,
        "lead": lead,
        "tables": tables or [],
        "quotes": quotes or [],
        "note": note,
    }


def question_pack(df):
    """Answer the research questions from confident tags. Empty data still returns every question."""
    questions = [
        "Why do people start a SIP, and what do they expect to happen?",
        "What changes in their behaviour in the months after starting?",
        "What leads investors to pause, reduce or stop a SIP?",
        "What do investors check, and how often, once they have started?",
        "What confuses or worries them inside the app?",
        "What do they do outside the app when they feel unsure?",
        "What separates investors who continue from those who quietly drop off?",
        "How do these patterns differ across user segments?",
        "What unmet needs emerge consistently across conversations?",
    ]
    ok = usable(df)
    needed = {
        "journey_stage",
        "tree_node",
        "action_taken",
        "trigger",
        "unmet_need",
        "what_they_check",
        "confusion_point",
        "emotion",
        "workaround_outside_app",
        "text",
        "income_type",
        "age_hint",
        "influenced_by",
    }
    if ok.empty or not needed.issubset(ok.columns):
        waiting = "No confident tags yet. This answer fills in as comments are tagged."
        return [_block(question, waiting) for question in questions]

    start = ok[ok["journey_stage"].astype(str).eq("start") | ok["tree_node"].isin(["A1", "A2"])]
    stop = ok[_actions(ok).isin(STOP_ACTIONS) | ok["tree_node"].astype(str).eq("C1")]
    keep = ok[_actions(ok).isin(KEEP_ACTIONS) | ok["tree_node"].astype(str).eq("D1")]
    start_triggers = _top(start, "trigger")
    start_needs = _top(start, "unmet_need")
    if start.empty:
        start_lead = "No confident comment is tagged at the start of a SIP yet."
    else:
        start_lead = f"{_comments(len(start))} {_verb(len(start), 'is', 'are')} tagged at the start of a SIP."
        if len(start_triggers):
            start_lead += f" The most common trigger is “{start_triggers.iloc[0]['trigger']}” ({int(start_triggers.iloc[0]['n'])})."
        start_lead += " What they expected is read from the unmet-need line on those same comments."

    behaviour = _behaviour_table(ok)
    if behaviour.empty:
        behaviour_lead = "No comment has a journey stage yet."
    else:
        behaviour_lead = (
            "Each row is a stage after the tagger placed the comment. "
            "Still investing means the comment says the SIP continued or restarted."
        )

    stop_triggers = _top(stop, "trigger")
    if stop.empty:
        stop_lead = "No confident comment describes a pause, a reduction, or a stop yet."
    else:
        stop_lead = f"{_comments(len(stop))} {_verb(len(stop), 'describes', 'describe')} a pause, a reduction, or a stop."
        if len(stop_triggers):
            stop_lead += f" The most common trigger is “{stop_triggers.iloc[0]['trigger']}” ({int(stop_triggers.iloc[0]['n'])})."

    checks = _top(ok, "what_they_check")
    named_rhythm, rhythm_counts = _check_rhythm(ok)
    rhythm = pd.DataFrame(
        [{"rhythm_mentioned": name, "n": count} for name, count in rhythm_counts.items() if count]
    )
    if checks.empty:
        check_lead = "No confident comment names what the person looks at after starting."
    else:
        check_lead = (
            f"The most common thing people name is “{checks.iloc[0]['what_they_check']}” "
            f"({_comments(int(checks.iloc[0]['n']))})."
        )
        if named_rhythm:
            check_lead += f" {_comments(named_rhythm)} {_verb(named_rhythm, 'talks', 'talk')} about checking. {_comments(int(rhythm['n'].sum()) if len(rhythm) else 0)} of those also name a rhythm."
        else:
            check_lead += " These comments name what people look at. They rarely say how often."

    confusion = _top(ok, "confusion_point")
    worry = ok[ok["emotion"].astype(str).isin(["confused", "anxious", "disappointed", "angry"])] if "emotion" in ok.columns else ok.iloc[0:0]
    emotions = _top(worry, "emotion")
    if confusion.empty and emotions.empty:
        confusion_lead = "No confident comment names a confusion or a worry yet."
    else:
        confusion_lead = f"{_comments(len(worry))} {_verb(len(worry), 'is', 'are')} tagged confused, anxious, disappointed, or angry."
        if len(confusion):
            confusion_lead += f" The most common confusion is “{confusion.iloc[0]['confusion_point']}” ({int(confusion.iloc[0]['n'])})."

    outside = _top(ok, "workaround_outside_app")
    if outside.empty:
        outside_lead = "No confident comment describes something the person did outside the app."
    else:
        outside_lead = (
            f"The most common step outside the app is “{outside.iloc[0]['workaround_outside_app']}” "
            f"({_comments(int(outside.iloc[0]['n']))})."
        )

    keep_triggers = _top(keep, "trigger")
    if keep.empty and stop.empty:
        split_lead = "No confident comment is tagged as either continuing or stopping."
    else:
        split_lead = (
            f"{_comments(len(keep))} {_verb(len(keep), 'says', 'say')} the SIP continued or restarted. "
            f"{_comments(len(stop))} {_verb(len(stop), 'says', 'say')} it was paused, reduced, or stopped. "
            + config.VOCAL_NOTE
        )

    segments = _segment_table(ok)
    unclear_income = 0
    if "income_type" in ok.columns:
        unclear_income = int(ok["income_type"].fillna("").astype(str).str.lower().isin(["", "unclear"]).sum())
    segment_lead = (
        "The split below uses only comments that state a segment. "
            f"{_comments(unclear_income)} {_verb(unclear_income, 'does', 'do')} not state income stability. "
        "Where the SIP money came from is not a separate tag."
    )

    needs = _top(ok, "unmet_need", limit=8)
    if needs.empty:
        needs_lead = "No unmet need has been tagged yet."
    else:
        needs_lead = (
            f"{_comments(int(needs['n'].sum()))} {_verb(int(needs['n'].sum()), 'shares', 'share')} the unmet needs below. "
            f"The most common line is “{needs.iloc[0]['unmet_need']}” ({int(needs.iloc[0]['n'])})."
        )

    return [
        _block(
            questions[0],
            start_lead,
            [("Triggers at the start", start_triggers), ("What those comments say was missing", start_needs)],
            _quotes(start),
            _slice_note(len(start)),
        ),
        _block(questions[1], behaviour_lead, [("By stage", behaviour)], _quotes(ok[ok["journey_stage"].astype(str).isin(["settle_in_m1_3", "middle_m4_9", "month_12_plus"])])),
        _block(
            questions[2],
            stop_lead,
            [("Triggers", stop_triggers), ("What they looked at", _top(stop, "what_they_check"))],
            _quotes(stop),
            _slice_note(len(stop)),
        ),
        _block(
            questions[3],
            check_lead,
            [("What they name", checks), ("Rhythm, only when the comment says it", rhythm)],
            _quotes(ok[ok["what_they_check"].astype(str).str.lower().isin(["app_value", "nav", "statement", "returns_calculator", "news"])] if "what_they_check" in ok.columns else ok.iloc[0:0]),
        ),
        _block(
            questions[4],
            confusion_lead,
            [("Confusion points", confusion), ("Worry in the tag", emotions)],
            _quotes(worry if len(worry) else ok),
        ),
        _block(questions[5], outside_lead, [("Outside the app", outside)], _quotes(ok.loc[_filled(ok["workaround_outside_app"]).index])),
        _block(
            questions[6],
            split_lead,
            [("Triggers among people who stayed", keep_triggers), ("Triggers among people who paused or stopped", stop_triggers)],
            _quotes(pd.concat([keep, stop], ignore_index=True) if len(keep) or len(stop) else ok.iloc[0:0]),
            config.VOCAL_NOTE,
        ),
        _block(
            questions[7],
            segment_lead,
            [("Income stability, age hint, and who influenced them", segments)],
            [],
            "Where the SIP money came from is not tagged. Income stability is the closest field.",
        ),
        _block(questions[8], needs_lead, [("Unmet needs", needs)], _quotes(ok.loc[_filled(ok["unmet_need"]).index])),
    ]


def _match_topic(question):
    """Pick the intent of the question. Time words like 'after a few months' do not override a stop or a start."""
    text = re.sub(r"[^a-z0-9\s]", " ", str(question).lower())
    topics = [
        ("stop", ["stop", "stopped", "stopping", "pause", "paused", "pausing", "cancel", "cancelled", "quit", "redeem", "redemption", "withdraw"]),
        ("start", ["start", "started", "starting", "begin", "expect", "expectation", "motivate"]),
        ("check", ["check", "checking", "often", "nav", "statement", "portfolio"]),
        ("confuse", ["confus", "worr", "anxious", "scared"]),
        ("outside", ["outside", "workaround"]),
        ("continue", ["continue", "continued", "drop off", "quietly"]),
        ("segment", ["segment", "income", "age", "salary", "influenc"]),
        ("unmet", ["unmet", "missing", "wish"]),
        ("behaviour", ["behaviour", "behavior", "settle"]),
    ]
    best = None
    best_score = 0
    for name, words in topics:
        score = 0
        for word in words:
            if re.search(r"\b" + re.escape(word), text):
                score += len(word)
        if score > best_score:
            best = name
            best_score = score
    if best is None and re.search(r"\b(after|month|months|later)\b", text):
        return "behaviour"
    return best


def _asks_about_later_months(question):
    return bool(re.search(r"\b(month|months|later|few|after)\b", str(question).lower()))


def _clip_words(text, limit=32):
    words = re.sub(r"\s+", " ", str(text)).strip().split()
    if not words:
        return ""
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]) + "…"


def _specificity(pattern):
    """Longer phrase = more specific. Used only as a tie-break between themes that both match."""
    parts = pattern.pattern.split("|")
    return max(len(part) for part in parts) if parts else 1


def _example_comment(frame, used_ids, used_quotes):
    """One unused comment. Returns clipped text and row id."""
    if frame.empty or "text" not in frame.columns:
        return "", ""
    ordered = frame
    if "confidence" in frame.columns:
        ordered = frame.assign(_confidence=pd.to_numeric(frame["confidence"], errors="coerce").fillna(0))
        ordered = ordered.sort_values("_confidence", ascending=False)
    fallback = ("", "")
    for idx, row in ordered.iterrows():
        row_id = str(row["id"]) if "id" in ordered.columns else str(idx)
        clipped = _clip_words(row["text"])
        if row_id in used_ids or clipped in used_quotes or len(clipped.split()) < 8:
            continue
        if not fallback[0]:
            fallback = (clipped, row_id)
        if 8 <= len(clipped.split()) <= 28:
            return clipped, row_id
    return fallback


def sip_was_stopped(text):
    """The comment says a SIP was cancelled or stopped. It does not look for a reason."""
    return bool(text and SIP_WORD.search(text) and SIP_STOP.search(text))


def cancelled_account_plan_or_app(text):
    """The comment cancels an account, a paid plan, or the app, and does not say a SIP was stopped."""
    if not text or sip_was_stopped(text):
        return False
    return bool(NON_SIP_CANCEL.search(text))


def reason_assignment(frame, themes=None):
    """One reason per comment. The longer matching phrase wins. Blank means no reason matched."""
    use_cancel_rules = themes is None
    themes = list(themes or REASON_THEMES)
    labels = pd.Series("", index=frame.index, dtype=object)
    also = pd.Series(False, index=frame.index)
    if frame.empty or "text" not in frame.columns:
        return labels, also
    order = {label: index for index, (label, _pattern) in enumerate(themes)}
    for idx, row in frame.iterrows():
        text = str(row.get("text", "") or "")
        hits = []
        for label, pattern in themes:
            if pattern.search(text):
                hits.append((_specificity(pattern), order[label], label))
        if hits:
            hits.sort(key=lambda item: (-item[0], item[1]))
            labels.at[idx] = hits[0][2]
            also.at[idx] = len(hits) > 1
            continue
        if not use_cancel_rules:
            continue
        if sip_was_stopped(text):
            labels.at[idx] = CANCELLED_NO_REASON
            also.at[idx] = bool(NON_SIP_CANCEL.search(text))
        elif cancelled_account_plan_or_app(text):
            labels.at[idx] = NOT_A_SIP_CANCEL
    return labels, also


def _reason_table(frame, limit=12, themes=None):
    """Count each comment under one reason. The more specific matching phrase wins."""
    columns = ["reason", "comments", "also_matched", "row_id", "example"]
    use_default = themes is None
    themes = list(themes or REASON_THEMES)
    if frame.empty or "text" not in frame.columns:
        return pd.DataFrame(columns=columns)
    labels, also = reason_assignment(frame, None if use_default else themes)
    extra_labels = (CANCELLED_NO_REASON, NOT_A_SIP_CANCEL)
    buckets = {label: [] for label, _pattern in themes}
    overlaps = {label: 0 for label, _pattern in themes}
    for label in extra_labels:
        buckets[label] = []
        overlaps[label] = 0
    unmatched = []
    for idx, label in labels.items():
        if not label:
            unmatched.append(idx)
            continue
        buckets[label].append(idx)
        if bool(also.at[idx]):
            overlaps[label] += 1
    rows = []
    used_ids = set()
    used_quotes = set()
    ordered_labels = [label for label, _pattern in themes] + list(extra_labels)
    for label in ordered_labels:
        indexes = buckets[label]
        if not indexes:
            continue
        example, row_id = _example_comment(frame.loc[indexes], used_ids, used_quotes)
        if row_id:
            used_ids.add(row_id)
        if example:
            used_quotes.add(example)
        rows.append(
            {
                "reason": label,
                "comments": len(indexes),
                "also_matched": overlaps[label],
                "row_id": row_id,
                "example": example,
            }
        )
    rows.sort(key=lambda item: item["comments"], reverse=True)
    if unmatched:
        example, row_id = _example_comment(frame.loc[unmatched], used_ids, used_quotes)
        rows.append(
            {
                "reason": "No matching reason",
                "comments": len(unmatched),
                "also_matched": 0,
                "row_id": row_id,
                "example": example,
            }
        )
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)


def _reason_sentence(reasons):
    if reasons.empty:
        return ""
    named = reasons[reasons["reason"] != "No matching reason"] if "reason" in reasons.columns else reasons
    bits = [f"{row.reason} ({int(row.comments)})" for row in named.head(3).itertuples()]
    if len(bits) == 1:
        listed = bits[0]
    elif len(bits) == 2:
        listed = f"{bits[0]} and {bits[1]}"
    else:
        listed = f"{bits[0]}, {bits[1]}, and {bits[2]}"
    return listed


def _reasons_block(question, frame, scope, extra_tables=None, note="", themes=None):
    asked = str(question).strip()
    reasons = _reason_table(frame, themes=themes)
    listed = _reason_sentence(reasons)
    if frame.empty:
        lead = "No confident comment matches this question yet."
    elif listed:
        lead = (
            f"Among {_comments(len(frame))} {scope}, the reasons that come up most are {listed}. "
            "Each comment is counted once. If it fits two reasons, it stays with the more specific one, "
            "and also_matched shows that overlap. The row id is the comment the example was copied from."
        )
    else:
        lead = (
            f"{_comments(len(frame))} {scope}, but they do not repeat one shared reason. "
            "The lines below are copied from those comments."
        )
    tables = [("Reasons in the comments", reasons)]
    quotes = []
    if reasons.empty:
        quotes = [_example_comment(frame.iloc[[i]]) for i in range(min(3, len(frame)))]
        quotes = [quote for quote in quotes if quote]
    else:
        tables.extend(extra_tables or [])
    return _block(asked, lead, tables, quotes, _slice_note(len(frame), note))


def _search_terms(question):
    stop = {
        "why", "do", "does", "people", "what", "the", "and", "how", "of", "to", "or",
        "in", "on", "they", "their", "them", "once", "have", "when", "who", "are",
        "from", "this", "that", "with", "for", "about", "after", "into", "across",
        "these", "those", "user", "users", "investor", "investors", "sip", "sips",
    }
    words = re.findall(r"[a-z0-9]{3,}", str(question).lower())
    return [word for word in words if word not in stop]


def _search_answer(df, question):
    asked = str(question).strip()
    ok = usable(df)
    if ok.empty:
        return _block(asked, "No confident tags yet. This answer fills in as comments are tagged.")
    terms = _search_terms(asked)
    if not terms:
        return _block(asked, "Ask about a behaviour, a worry, or a moment in the SIP. The comments can be searched for those words.")
    mask = pd.Series(False, index=ok.index)
    searchable = [column for column in ("text", "trigger", "confusion_point", "unmet_need", "evidence_quote") if column in ok.columns]
    if not searchable:
        return _block(asked, "No comment text is available to search yet.")
    for column in searchable:
        values = ok[column].fillna("").astype(str).str.lower()
        for term in terms:
            mask = mask | values.str.contains(re.escape(term), regex=True)
    found = ok[mask]
    if found.empty:
        return _block(
            asked,
            "No tagged comment matches those words yet. Try a question about starting, pausing, checking, or a worry inside the app.",
        )
    return _reasons_block(asked, found, "that use those words")


def _question_slice(ok, question, topic):
    """The comments that can answer this question, plus a plain description of that set."""
    if topic == "stop":
        frame = ok[_actions(ok).isin(STOP_ACTIONS) | ok["tree_node"].astype(str).eq("C1")]
        scope = "about a pause, a reduction, or a stop"
        note = ""
        if _asks_about_later_months(question):
            later = frame[frame["journey_stage"].astype(str).isin(LATER_STAGES)]
            if len(later) >= 20:
                frame = later
                scope = "about a pause or a stop after the SIP had already been running"
                note = "Comments that never say which month are left out of this answer."
        return frame, scope, note, []
    if topic == "start":
        frame = ok[ok["journey_stage"].astype(str).eq("start") | ok["tree_node"].isin(["A1", "A2"])]
        return frame, "tagged at the start of a SIP", "", []
    if topic == "behaviour":
        frame = ok[ok["journey_stage"].astype(str).isin(LATER_STAGES | {"restart"})]
        return frame, "placed after the SIP had started", "", [("By stage", _behaviour_table(frame if len(frame) else ok))]
    if topic == "check":
        named = ok["what_they_check"].astype(str).str.lower().isin(["app_value", "nav", "statement", "returns_calculator", "news"])
        frame = ok[named]
        return frame, "that name what the person looks at", "These comments rarely say how often.", []
    if topic == "confuse":
        worry = ok["emotion"].astype(str).isin(["confused", "anxious", "disappointed", "angry"])
        frame = ok[worry]
        return frame, "tagged as confused, anxious, disappointed, or angry", "", []
    if topic == "outside":
        frame = ok.loc[_filled(ok["workaround_outside_app"]).index]
        return frame, "that name a step outside the app", "", []
    if topic == "continue":
        stop = ok[_actions(ok).isin(STOP_ACTIONS) | ok["tree_node"].astype(str).eq("C1")]
        keep = ok[_actions(ok).isin(KEEP_ACTIONS) | ok["tree_node"].astype(str).eq("D1")]
        return stop, "about a pause, a reduction, or a stop", config.VOCAL_NOTE, [("Reasons among people who stayed", _reason_table(keep, themes=START_THEMES))]
    if topic == "segment":
        return ok, "in the confident set", "Where the SIP money came from is not tagged. Income stability is the closest field.", [("Income stability, age hint, and who influenced them", _segment_table(ok))]
    if topic == "unmet":
        needs = _top(ok, "unmet_need", limit=20)
        if len(needs):
            keep = ~needs["unmet_need"].astype(str).str.contains(JUNK_REASON, na=False)
            needs = needs[keep].head(6)
        return ok, "in the confident set", "", [("What the tag says was missing", needs)]
    return ok.iloc[0:0], "comments", "", []


def answer_question(df, question):
    """Answer one free-text question from the comment text, leading with the reasons people give."""
    asked = str(question).strip()
    if not asked:
        return _block("", "Enter a question first.")
    ok = usable(df)
    if ok.empty:
        return _block(asked, "No confident tags yet. This answer fills in as comments are tagged.")
    topic = _match_topic(asked)
    if topic is None:
        return _search_answer(df, asked)
    if topic == "segment":
        block = dict(question_pack(df)[7])
        block["question"] = asked
        return block
    frame, scope, note, extra = _question_slice(ok, asked, topic)
    themes = START_THEMES if topic == "start" else None
    return _reasons_block(asked, frame, scope, extra, note, themes=themes)


def ranking_line(df):
    ranking = build_ranking(df)
    usable_n = len(usable(df))
    if ranking.empty or "slice_type" not in ranking.columns:
        return f"confident {usable_n}; no ranking", ranking
    overall = ranking[ranking["slice_type"] == "all"].sort_values("score", ascending=False)
    bits = [f"{row.tree_node} n={int(row.n)} score={row.score}" for row in overall.itertuples()]
    return f"confident {usable_n}; " + "; ".join(bits), ranking


def print_report(df):
    ok = usable(df)
    print(f"Rows in the score: {len(ok)}")
    print(SEVERITY_SENTENCE)
    print(config.VOCAL_NOTE)
    print("\nQuestions:")
    for block in question_pack(df):
        print(block["question"])
        print("  " + block["lead"])
    ranking = build_ranking(df)
    overall = ranking[ranking["slice_type"] == "all"] if len(ranking) else ranking
    if overall.empty:
        print("No scored rows yet.")
        return ranking
    print("\nOpportunity ranking (all comments):")
    show = overall[["tree_node", "n", "frequency", "severity", "fixability", "score", "note"]]
    print(show.to_string(index=False))
    print("\nVoluntary and involuntary by stage:")
    split = stage_split(df)
    if len(split):
        print(split.to_string(index=False))
    print("\nTop confusion points:")
    print(top_counts(df, "confusion_point").to_string(index=False))
    print("\nTop unmet needs:")
    print(top_counts(df, "unmet_need").to_string(index=False))
    print("\nTop workarounds:")
    print(top_counts(df, "workaround_outside_app").to_string(index=False))
    print("\nGroww, competitors, and YouTube:")
    mix = brand_mix(df)
    if len(mix):
        print(mix.head(30).to_string(index=False))
    print("\nQuotes:")
    for node, quotes in quotes_by_node(df).items():
        print(f"  {node}")
        for quote in quotes:
            print("    - " + mask_fund_names(quote)[0])
    return ranking


def short_masked_quotes(df, node, limit):
    ok = usable(df)
    if ok.empty:
        return []
    part = ok[ok["tree_node"].astype(str) == node]
    if "confidence" in part.columns:
        part = part.sort_values("confidence", ascending=False)
    found = []
    seen = set()
    for _, row in part.iterrows():
        quote = str(row.get("evidence_quote") or "").strip()
        if not quote or len(quote.split()) > 15 or quote in seen:
            continue
        masked, _changed = mask_fund_names(quote)
        if not masked or len(masked.split()) > 15:
            continue
        seen.add(quote)
        app = str(row.get("app") or "").strip()
        if app.lower() in ("", "nan", "none"):
            app = "YouTube, no app named"
        found.append({"id": row.get("id", ""), "app": app, "quote": masked})
        if len(found) == limit:
            break
    return found


def _yes_no(flag):
    return "yes" if flag else "no"


def write_problem_candidates(df):
    """Top 4 in-scope nodes by score, excluding none. No best-problem label."""
    ok = usable(df)
    if ok.empty:
        return pd.DataFrame()
    scope = ok[ok["metric_scope"].astype(str) == "in_scope"] if "metric_scope" in ok.columns else ok
    ranking = build_ranking(scope)
    if ranking.empty:
        return pd.DataFrame()
    overall = ranking[(ranking["slice_type"] == "all") & (ranking["tree_node"].astype(str) != "none")]
    overall = overall.sort_values("score", ascending=False).head(4)
    groww = scope[scope["app"].fillna("").astype(str).str.strip().eq("Groww")] if "app" in scope.columns else scope.iloc[0:0]
    base = len(scope)
    records = []
    for row in overall.itertuples():
        node = row.tree_node
        part = scope[scope["tree_node"].astype(str) == node]
        groww_part = groww[groww["tree_node"].astype(str) == node] if not groww.empty else groww
        ended = 0
        if "sip_outcome" in part.columns and len(part):
            ended = int(part["sip_outcome"].astype(str).eq("ended").sum())
        confusion = top_counts(part, "confusion_point", limit=3)
        workaround = top_counts(part, "workaround_outside_app", limit=3)
        quotes = short_masked_quotes(scope, node, 3)
        fix = config.FIXABILITY.get(node, config.FIXABILITY["none"])
        reason = str(fix["reason"])
        quote_text = " ".join(item["quote"] for item in quotes)
        fear = any(phrase in (reason + " " + quote_text).lower() for phrase in config.FEAR_PHRASES)
        advice = bool(re.search(r"\b(buy|sell|stay invested|you should)\b", reason, re.I))
        raw_quotes = []
        for item in quotes:
            raw_quotes.append(item["quote"])
        named = any(mask_fund_names(text)[1] for text in [reason] + raw_quotes)
        records.append(
            {
                "node": node,
                "moment": config.TREE.get(node, ""),
                "n_groww": int(len(groww_part)),
                "n_all": int(len(part)),
                "share_of_in_scope": round(len(part) / base, 4) if base else 0,
                "share_sip_outcome_ended": round(ended / len(part), 4) if len(part) else 0,
                "top_confusion": "; ".join(confusion.iloc[:, 0].astype(str).tolist()) if len(confusion) else "",
                "top_workarounds": "; ".join(workaround.iloc[:, 0].astype(str).tolist()) if len(workaround) else "",
                "quotes": " | ".join(f"{item['id']} [{item['app']}] {item['quote']}" for item in quotes),
                "fixability": fix["score"],
                "fixability_reason": reason,
                "fixable_in_app_without_advice": _yes_no(not advice),
                "without_fear_or_fomo": _yes_no(not fear),
                "without_naming_a_fund": _yes_no(not named),
            }
        )
    out = pd.DataFrame(records)
    config.write_csv(out, config.DATA_DIR / "problem_candidates.csv")
    print("\nProblem candidates (no best label):")
    if len(out):
        print(out.to_string(index=False))
    print(f"Wrote {config.DATA_DIR / 'problem_candidates.csv'}")
    return out


def main():
    retag_path = config.DATA_DIR / "final_retag.csv"
    retag = config.read_csv(retag_path) if retag_path.exists() else pd.DataFrame()
    if retag.empty:
        print("No retagged rows in final_retag.csv. Older tags in final.csv were not scored.")
        return
    print(f"Scoring only the {len(retag)} rows in final_retag.csv. Older tags were not included.")
    if "app" in retag.columns:
        apps = retag["app"].fillna("").astype(str).str.strip().replace("", "(no app)")
        print("Rows by app:")
        print(apps.value_counts().to_string())
    before = config.read_csv(config.FINAL_CSV)
    before_line, _before_ranking = ranking_line(before) if not before.empty else ("no previous file", None)
    print("Previous full file, not used for this score: " + before_line)
    ranking = print_report(retag)
    if ranking is not None and len(ranking):
        config.write_csv(ranking, config.RANKING_CSV)
        print(f"\nWrote {config.RANKING_CSV}")
    after_line, _after_ranking = ranking_line(retag)
    print("Retagged rows: " + after_line)
    write_problem_candidates(retag)
    log_path = config.DATA_DIR / "changes_log.csv"
    with log_path.open("a", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "change", "reason", "rows_affected", "before_summary", "after_summary"],
        )
        writer.writerow(
            {
                "date": date.today().isoformat(),
                "change": "Scored severity from sip_outcome on final_retag.csv only",
                "reason": "Severity is 3 when the SIP ended, 2 when it was paused, reduced, or the person is considering stopping, and 1 when the SIP is still continuing. A failed debit that the comment does not say ended the SIP is not severity 3. Frequency and fixability were not changed. Older tags were not mixed in.",
                "rows_affected": int(len(retag)),
                "before_summary": "Previous full file, not scored. " + before_line,
                "after_summary": after_line + " " + SEVERITY_SENTENCE,
            }
        )


if __name__ == "__main__":
    main()
