"""Steps 1 to 5 for one user message. At most two model calls."""

from chat.agents import answer, answer_general, load_kb, retrieve, score_entry, usable
from chat.config import CONFIDENCE_MIN
from chat.language import detect_language, reply_instruction, safety_text
from chat.router import route
from chat.safety import LIMITED_TEXT, check_output, mask, precheck, reply_has_blocked_detail


def _titles(entries):
    return [entry.get("title") or entry.get("id") for entry in entries]


def _clarifiers(entries):
    for entry in entries:
        items = [item for item in (entry.get("clarifiers") or []) if item]
        if items:
            return items[:3]
    return []


def _source(entries):
    for entry in entries:
        title = (entry.get("source_title") or "").strip()
        url = (entry.get("source_url") or "").strip()
        if title and not title.upper().startswith("TODO-VERIFY"):
            if url.upper().startswith("TODO-VERIFY"):
                url = ""
            return title, url
    return "", ""


def _base(action, text, agent, entries, confidence, low, reason=""):
    title, url = _source(entries)
    return {
        "action": action,
        "agent": agent,
        "text": text,
        "reason": reason,
        "kb_ids": [entry.get("id") for entry in entries],
        "kb_titles": _titles(entries),
        "clarifiers": _clarifiers(entries),
        "source_title": title,
        "source_url": url,
        "confidence": confidence,
        "low": low,
    }


def fallback(agent, entries, reason, confidence=0, low=False, language="english"):
    title, url = _source(entries)
    text = safety_text(language, "fallback")
    if title:
        text = safety_text(
            language,
            "fallback_source",
            title=title,
            url=(", " + url) if url else "",
        )
    elif entries and not any(usable(entry) for entry in entries):
        text = (
            "I'm not sure about this one, and I don't want to guess. "
            "The notes for this topic are not filled in from an official page yet. "
            "I can pass this to support."
        )
    result = _base("fallback", text, agent, entries, confidence, low, reason)
    result["source_title"] = title
    result["source_url"] = url
    return result


def prefer_scheme(agent, message, scenario, kb):
    """Use the scheme notes when the message names one, even if the router said learn or none."""
    if agent in {"instalment", "controls", "handoff"}:
        return agent
    best_score = 0
    catalog_score = 0
    for entry in kb:
        if entry.get("agent") != "scheme":
            continue
        score = score_entry(entry, message, scenario)
        if entry.get("id") == "scheme_catalog":
            catalog_score = score
        elif score > best_score:
            best_score = score
    if best_score >= 1 or catalog_score >= 1:
        return "scheme"
    return agent


def _limited(agent, confidence):
    return _base("limited", LIMITED_TEXT, agent, [], confidence, False, "blocked detail")


def _accept(
    payload,
    agent,
    entries,
    rows,
    confidence,
    require_kb,
    word_cap,
    extra_names=None,
    language="english",
):
    draft = payload.get("answer") or ""
    if reply_has_blocked_detail(draft):
        return _limited(agent, confidence)
    if not payload.get("answerable"):
        return fallback(agent, [], "model unsure", confidence, language=language)
    known = {entry.get("id") for entry in rows}
    ok, reason = check_output(
        payload,
        known,
        max_words=word_cap,
        require_kb=require_kb,
        extra_names=extra_names,
    )
    if not ok:
        return fallback(
            agent,
            [],
            reason,
            payload.get("confidence") or 0,
            low=(reason == "low confidence"),
            language=language,
        )
    if require_kb:
        used = payload.get("kb_ids_used") or []
        used_entries = [entry for entry in entries if entry.get("id") in used]
        chosen = used_entries or entries
    else:
        chosen = []
    return _base(
        "answer",
        (payload.get("answer") or "").strip(),
        agent,
        chosen,
        float(payload.get("confidence")),
        False,
    )


def run_turn(message, context, llm=None, kb=None):
    """Run one turn. llm and kb are injectable so tests do not call NVIDIA."""
    masked, _changed = mask(message)
    language_code = detect_language(masked)
    language = reply_instruction(language_code)
    early = precheck(masked)
    if early is not None:
        if early.get("action") == "decline":
            early = dict(early)
            early["text"] = safety_text(language_code, "decline")
        return early

    rows = kb if kb is not None else load_kb()
    scenario = (context or {}).get("scenario") or ""
    try:
        routed = route(masked, context or {}, llm=llm)
    except Exception:
        return fallback("none", [], "router failed", 0, language=language_code)

    agent = routed["agent"]
    if routed["confidence"] < CONFIDENCE_MIN:
        return fallback(agent, [], "router unsure", routed["confidence"], low=True, language=language_code)

    if agent == "news":
        return _limited("none", routed["confidence"])
    agent = prefer_scheme(agent, masked, scenario, rows)
    lookup_agent = "general" if agent == "none" else agent
    entries = retrieve(lookup_agent, masked, scenario, kb=rows)
    verified = [entry for entry in entries if usable(entry)]
    word_cap = 170 if agent == "scheme" else None
    try:
        if verified:
            payload = answer(masked, context or {}, verified, language, llm=llm)
            return _accept(
                payload,
                agent,
                verified,
                rows,
                routed["confidence"],
                True,
                word_cap,
                language=language_code,
            )
        payload = answer_general(masked, context or {}, language, llm=llm)
    except Exception:
        return fallback(agent, [], "answer failed", routed["confidence"], language=language_code)
    return _accept(
        payload, agent, [], rows, routed["confidence"], False, word_cap, language=language_code
    )


def apply_streaks(result, low_streak, decline_streak):
    """Turn a second low-confidence or second decline in a row into a handoff."""
    action = result.get("action")
    if action == "decline":
        decline_streak += 1
        low_streak = 0
        if decline_streak >= 2:
            result = dict(result)
            result["action"] = "handoff"
            result["text"] = ""
            result["reason"] = "safety check declined twice"
        return result, low_streak, decline_streak
    if result.get("low"):
        low_streak += 1
        decline_streak = 0
        if low_streak >= 2:
            result = dict(result)
            result["action"] = "handoff"
            result["text"] = ""
            result["reason"] = "low confidence"
        return result, low_streak, decline_streak
    if action in ("answer", "none"):
        return result, 0, 0
    return result, low_streak, decline_streak
