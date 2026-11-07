"""Route one message. This is AI call number 1."""

import json
from pathlib import Path

from chat.llm import complete

PROMPT = (Path(__file__).resolve().parent / "prompts" / "router.txt").read_text().strip()
AGENTS = {"instalment", "controls", "learn", "scheme", "news", "none"}


def first_json(text):
    raw = text or ""
    start = raw.find("{")
    if start < 0:
        raise ValueError("no json")
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(raw)):
        char = raw[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(raw[start : index + 1])
    raise ValueError("incomplete json")


def route(message, context, llm=None):
    caller = llm or complete
    user = "Context:\n" + json.dumps(context, ensure_ascii=True) + "\n\nUser message:\n" + message
    text = caller(PROMPT, user, 180)
    data = first_json(text)
    agent = str(data.get("agent") or "").strip().lower()
    if agent not in AGENTS:
        agent = "none"
    try:
        confidence = float(data.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.0
    language = str(data.get("language") or "english").strip().lower()
    if language not in {"english", "hinglish"}:
        language = "english"
    return {"agent": agent, "confidence": confidence, "language": language}
