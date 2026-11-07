"""Safety checks that do not call a model: decline list, output check, masking."""

import json
import re
from pathlib import Path

from chat.config import CONFIDENCE_MIN, MAX_ANSWER_WORDS

HERE = Path(__file__).resolve().parent

PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)")
LONG_DIGITS_RE = re.compile(r"\d{6,}")
FUND_RE = re.compile(
    r"\b[A-Z][A-Za-z0-9&+-]*(?:\s+[A-Z][A-Za-z0-9&+-]*)*\s+"
    r"(?:Index Fund|Flexi Cap|Mid Cap|Small Cap|ELSS|Fund)\b"
)

DECLINE_RES = [
    re.compile(pattern, re.I)
    for pattern in (
        r"which fund",
        r"best fund",
        r"best sip",
        r"which stock",
        r"best stock",
        r"konsa fund",
        r"kaunsa fund",
        r"kaun sa fund",
        r"konsa stock",
        r"kaunsa stock",
        r"should i buy",
        r"should i sell",
        r"should i stop",
        r"should i invest",
        r"right time",
        r"sahi time",
        r"will the market",
        r"will it go up",
        r"kitna return milega",
        r"guaranteed",
    )
]

HANDOFF_RES = [
    re.compile(pattern, re.I)
    for pattern in (
        r"\bagent\b",
        r"\bhuman\b",
        r"\bsupport\b",
        r"talk to someone",
        r"\binsaan\b",
        r"customer care",
    )
]

DECLINE_TEXT = (
    "I can't suggest funds or stocks, or say what to buy, sell or when. "
    "That needs a registered adviser. I can help with SIP instalments, "
    "SIP controls, what SIP terms mean, and the published figures for the "
    "SIP schemes in these notes. Want to try one of those?"
)
MASK_NOTE = "Please don't share account numbers, PAN or phone numbers here. I've hidden it."
FALLBACK_TEXT = (
    "I'm not sure about this one, and I don't want to guess. "
    "You can check the official source, or I can pass this to support."
)
NONE_TEXT = (
    "I can help with SIP instalments, SIP controls, what SIP terms mean, "
    "and the published figures for the SIP schemes in these notes."
)
LIMITED_TEXT = (
    "I can't share news, returns or fund details. "
    "I can help with your SIP instalment or explain how SIPs work."
)
ASK_DETAIL_RE = re.compile(
    r"\b(news|headlines?|samachar|khabar|returns?|funds?)\b",
    re.I,
)
RETURN_PCT_RE = re.compile(
    r"(?:\breturns?\b.{0,40}%|%.{0,40}\breturns?\b)",
    re.I | re.S,
)


def blocked_terms():
    path = HERE / "blocked_terms.txt"
    terms = []
    for line in path.read_text().splitlines():
        item = line.strip().lower()
        if item and not item.startswith("#"):
            terms.append(item)
    return terms


def mask(text):
    """Hide PAN, email, phone, and any run of 6 or more digits."""
    original = "" if text is None else str(text)
    masked = PAN_RE.sub("[hidden]", original)
    masked = EMAIL_RE.sub("[hidden]", masked)
    masked = PHONE_RE.sub("[hidden]", masked)
    masked = LONG_DIGITS_RE.sub("[hidden]", masked)
    return masked, masked != original


def wants_person(text):
    lowered = (text or "").lower()
    return any(pattern.search(lowered) for pattern in HANDOFF_RES)


def asks_blocked_topic(text):
    """News, returns, or a fund name. These never go to the model."""
    return bool(ASK_DETAIL_RE.search(text or ""))


def reply_has_blocked_detail(text):
    """A drafted reply that states a return percentage or names a fund."""
    raw = text or ""
    if RETURN_PCT_RE.search(raw):
        return True
    return bool(FUND_RE.search(raw))


def is_advice_request(text):
    """True when the user asks what they should do, not how a control works."""
    lowered = (text or "").lower()
    return any(pattern.search(lowered) for pattern in DECLINE_RES)


def precheck(text):
    """Return a result dict, or None when the message can go to the router."""
    if wants_person(text):
        return {
            "action": "handoff",
            "agent": "handoff",
            "text": "",
            "reason": "user asked for support",
            "kb_ids": [],
            "kb_titles": [],
            "clarifiers": [],
            "source_title": "",
            "source_url": "",
            "confidence": 1,
            "low": False,
        }
    if asks_blocked_topic(text) and not is_advice_request(text):
        return {
            "action": "limited",
            "agent": "none",
            "text": LIMITED_TEXT,
            "reason": "news returns or fund details",
            "kb_ids": [],
            "kb_titles": [],
            "clarifiers": [],
            "source_title": "",
            "source_url": "",
            "confidence": 1,
            "low": False,
        }
    if is_advice_request(text):
        return {
            "action": "decline",
            "agent": "none",
            "text": DECLINE_TEXT,
            "reason": "advice request",
            "kb_ids": [],
            "kb_titles": [],
            "clarifiers": [],
            "source_title": "",
            "source_url": "",
            "confidence": 1,
            "low": False,
        }
    return None


def find_blocked(text):
    lowered = (text or "").lower()
    for term in blocked_terms():
        if term in lowered:
            return term
    return ""


def allowed_scheme_names():
    """Official names copied into schemes.json. Other fund names stay blocked."""
    path = HERE / "schemes.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    names = []
    for row in data.get("schemes") or []:
        names.append(row.get("name") or "")
        names.extend(row.get("aliases") or [])
    names = [name.strip() for name in names if name and name.strip()]
    names.sort(key=len, reverse=True)
    return names


def has_fund_name(text, allowed=None):
    cleaned = text or ""
    for name in allowed if allowed is not None else allowed_scheme_names():
        cleaned = re.sub(re.escape(name), " ", cleaned, flags=re.I)
    return bool(FUND_RE.search(cleaned))


def word_count(text):
    return len(re.findall(r"\S+", text or ""))


def check_output(payload, known_ids, max_words=None, require_kb=True, extra_names=None):
    """Return (ok, reason). The disclaimer is added later by the screen, not here."""
    ids = payload.get("kb_ids_used") or []
    if require_kb and not ids:
        return False, "no kb id"
    for item_id in ids:
        if item_id not in known_ids:
            return False, "unknown kb id"
    try:
        confidence = float(payload.get("confidence"))
    except (TypeError, ValueError):
        return False, "low confidence"
    if confidence < CONFIDENCE_MIN:
        return False, "low confidence"
    answer = payload.get("answer") or ""
    if find_blocked(answer):
        return False, "blocked wording"
    names = None
    if extra_names:
        names = allowed_scheme_names() + [name for name in extra_names if name]
        names.sort(key=len, reverse=True)
    if has_fund_name(answer, allowed=names):
        return False, "fund name"
    limit = MAX_ANSWER_WORDS if max_words is None else max_words
    if word_count(answer) > limit:
        return False, "too long"
    return True, ""
