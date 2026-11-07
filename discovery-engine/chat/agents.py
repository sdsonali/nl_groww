"""Knowledge retrieval and the answer call (AI call number 2)."""

import json
from pathlib import Path

from chat.llm import complete
from chat.router import first_json

HERE = Path(__file__).resolve().parent
ANSWER_PROMPT = (HERE / "prompts" / "answer.txt").read_text().strip()
GENERAL_PROMPT = (HERE / "prompts" / "general.txt").read_text().strip()


def load_kb(path=None):
    raw = Path(path or (HERE / "kb.json")).read_text()
    return json.loads(raw)


def is_verified_fact(fact):
    text = (fact or "").strip()
    return bool(text) and not text.upper().startswith("TODO-VERIFY")


def usable(entry):
    return any(is_verified_fact(fact) for fact in entry.get("facts") or [])


def verified_view(entry):
    """Facts and steps with placeholders removed, so they are never shown as truth."""
    copy = dict(entry)
    copy["facts"] = [fact for fact in entry.get("facts") or [] if is_verified_fact(fact)]
    copy["steps"] = [
        step for step in entry.get("steps") or [] if is_verified_fact(step)
    ]
    return copy


def _keyword_hits(entry, message):
    text = (message or "").lower()
    hits = 0
    for keyword in entry.get("keywords") or []:
        cleaned = (keyword or "").strip().lower()
        if cleaned and cleaned in text:
            hits += max(1, len(cleaned.split()))
    return hits


def score_entry(entry, message, scenario):
    hits = _keyword_hits(entry, message)
    scenarios = entry.get("scenarios") or []
    if scenario and scenario in scenarios:
        hits += 2
    return hits


def retrieve(agent, message, scenario, kb=None, limit=3):
    """Top entries for this agent. An empty list means nothing matched."""
    rows = kb if kb is not None else load_kb()
    ranked = []
    for entry in rows:
        if entry.get("agent") != agent:
            continue
        score = score_entry(entry, message, scenario)
        if score > 0:
            ranked.append((score, entry))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    if not ranked or ranked[0][0] == 0:
        return []
    return [entry for _score, entry in ranked[:limit]]


def starter_entries(scenario, kb=None, limit=3):
    rows = kb if kb is not None else load_kb()
    chosen = [entry for entry in rows if scenario and scenario in (entry.get("scenarios") or [])]
    for entry in rows:
        if entry.get("agent") != "instalment":
            continue
        if entry not in chosen:
            chosen.append(entry)
        if len(chosen) >= limit:
            break
    return chosen[:limit]


def answer(message, context, entries, language, llm=None):
    caller = llm or complete
    packed = [verified_view(entry) for entry in entries if usable(entry)]
    user = (
        "Context:\n"
        + json.dumps(context, ensure_ascii=True)
        + "\n\nLanguage: "
        + language
        + "\n\nKB entries:\n"
        + json.dumps(packed, ensure_ascii=True)
        + "\n\nUser message:\n"
        + message
    )
    text = caller(ANSWER_PROMPT, user, 550)
    return first_json(text)


def answer_general(message, context, language, llm=None):
    """Answer from the prompt and guardrails when no checked note exists."""
    caller = llm or complete
    user = (
        "Context:\n"
        + json.dumps(context, ensure_ascii=True)
        + "\n\nLanguage: "
        + language
        + "\n\nNo checked notes are available for this question.\n\nUser message:\n"
        + message
    )
    text = caller(GENERAL_PROMPT, user, 400)
    return first_json(text)
