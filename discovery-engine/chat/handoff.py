"""Simulated support summary. Nothing here is written to disk."""

import random

from chat.config import SUPPORT_URL
from chat.safety import mask


def summary(scenario, user_message, agent, titles, reason):
    masked, _changed = mask(user_message or "")
    title_line = ", ".join(titles) if titles else "none"
    return (
        "Screen: SIP instalment recovery\n"
        "Scenario selected: " + (scenario or "not selected") + "\n"
        "User question (masked): " + masked + "\n"
        "Agent that answered: " + (agent or "none") + "\n"
        "Answers tried: " + title_line + "\n"
        "Reason for handoff: " + (reason or "user asked for support")
    )


def new_ticket_id():
    return "SIP-" + str(random.randint(100000, 999999))


def support_link():
    if not SUPPORT_URL or SUPPORT_URL.upper().startswith("TODO-VERIFY"):
        return ""
    return SUPPORT_URL
