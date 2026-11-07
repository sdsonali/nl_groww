"""Relevance check and metric-tree tagging through the Hugging Face API.

No model weights are downloaded. Responses are cached in data/cache.json.

    python 3_filter_tag.py
    python 3_filter_tag.py --limit 200
"""

import argparse
import json
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait

import pandas as pd
import requests

import config

PROMPT_VERSION = "v1"
RELEVANCE_BATCH = 20
TAG_BATCH = 5
RETAG_TEMPERATURE = 0
RETAG_MAX_TOKENS = 3200
# The 105-row post-hoc pass took about 82 seconds per batch of 5, including retries.
RETAG_SECONDS_PER_BATCH = 82
SIP_OUTCOMES = ("ended", "paused_or_reduced", "continuing", "unclear")
TENURE_HINTS = ("new", "under_3_months", "3_to_12_months", "over_12_months", "restart", "unclear")
TENURE_TO_STAGE = {
    "new": "start",
    "under_3_months": "settle_in_m1_3",
    "3_to_12_months": "middle_m4_9",
    "over_12_months": "month_12_plus",
    "restart": "restart",
    "unclear": "unclear",
}
COMPACT_MAX_ONE = 240
COMPACT_MAX_FIVE = 800
PARALLEL_WORKERS = 5
COMPETITOR_APPS = ("Zerodha Coin", "ET Money", "Kuvera", "Paytm Money", "INDmoney")

TAG_SYSTEM = """You tag public comments about SIP (a fixed amount invested every month in a mutual fund).
You are not an advisor. Never name a fund or a stock. Never tell someone to buy, sell, stay, or hurry.
Use only the comment text. If a detail is not in the text, use "unclear" or "none" and a low confidence. Never guess.
Separate a market move ("NAV went down") from a system failure ("my SIP debit failed").
Handle Hinglish and sarcasm.
Return JSON only, with no markdown.

Schema for each comment:
{
  "id": "c1",
  "is_relevant": true,
  "journey_stage": "start | settle_in_m1_3 | middle_m4_9 | month_12_plus | restart | unclear",
  "tree_node": "A1 | A2 | B1 | B2 | C1 | C2 | C3 | D1 | E1 | none",
  "leak_type": "voluntary | involuntary | none | unclear",
  "action_taken": "paused | cancelled | reduced | continued | failed_debit | restarted | considering | none",
  "trigger": "short phrase or null",
  "confusion_point": "short phrase or null",
  "what_they_check": "app_value | nav | statement | returns_calculator | news | none | unclear",
  "workaround_outside_app": "google | youtube | friends_family | advisor | calculator | other | none",
  "income_type": "salaried | irregular | student | unclear",
  "age_hint": "under_25 | 25_35 | 35_plus | unclear",
  "influenced_by": "friend | youtuber | app_nudge | family | self | unclear",
  "emotion": "confused | anxious | disappointed | neutral | satisfied | angry",
  "unmet_need": "one line in the user's own words",
  "evidence_quote": "exact substring of the comment, 15 words or fewer",
  "confidence": 0.0,
  "metric_scope": "in_scope | exit_experience | other_platform_complaint | unclear",
  "is_sip_instalment_issue": "yes | no | unclear",
  "sip_outcome": "ended | paused_or_reduced | continuing | unclear"
}

Every result must include is_sip_instalment_issue and sip_outcome. Use only those exact words.

metric_scope:
- in_scope: the comment is about starting, continuing, pausing, reducing, failing, restarting, or understanding a SIP instalment while the person is still investing or deciding whether to continue. An attempt to cancel, stop, pause, or reduce their own SIP is in_scope.
- exit_experience: the person has already decided to leave and the comment is about the exit itself (redemption speed, withdrawal delay, account closure, post-exit support).
- other_platform_complaint: complaints about fees, paid plans, reports, KYC, UI bugs, or other features that do not mention a SIP instalment, a pause, or a stop.
- unclear: cannot tell.

is_sip_instalment_issue: Does this comment clearly say a recurring SIP instalment, autopay, or mandate failed, was missed, or was not debited? A one-time payment, add-money failure, or login/KYC error is no.
- yes: a recurring SIP instalment, autopay, or mandate failed, was missed, or was not debited.
- no: a one-time payment, add-money failure, login, or KYC error, or the comment does not clearly say a recurring instalment failed.
- unclear: cannot tell.

sip_outcome: what happened to the SIP itself.
- ended: the SIP stopped, was cancelled, or lapsed, and the commenter does not say they restarted it. Severity uses this only when the SIP itself ended.
- paused_or_reduced: the SIP was paused or reduced, or the commenter is considering stopping.
- continuing: the commenter is confused or complaining but the SIP is still going. A failed debit is continuing when they do not say the SIP ended. An attempt to stop that did not succeed is continuing.
- unclear: cannot tell. A failed debit with no statement that the SIP ended may be unclear instead of ended.

Tree:
A1 setting up a SIP, or its first debit, including when that first debit fails. Not a later instalment.
A2 setup abandoned before the SIP is running
B1 the 2nd or 3rd instalment, including when that instalment has a problem
B2 user reacts to the first statement or the first look at value
C1 user pauses, cancels, reduces, or redeems, including an attempt to do so that did not succeed
C2 a problem paying, completing, or processing an instalment of a SIP that is already set up: debit failed, mandate expired, bank changed, balance was low, or the SIP repeatedly fails even when the balance is enough
C3 user fixed a failed debit
D1 still investing around month 12
E1 user restarted after a pause or a failure

A1 and A2 are only for setting up a SIP or its first debit. A problem paying, completing, or processing an instalment of a SIP that is already set up is C2, or B1 when the comment clearly says it is the 2nd or 3rd instalment. A SIP that repeatedly fails even when the balance is enough is C2.

Any tree_node other than none requires that the commenter describes something that happened to their own SIP: it was started or an attempt to start was made, a debit failed, they stopped, cancelled, paused, reduced, or restarted it, or they tried to do one of those.
Attempted actions count as events. If the commenter says they tried to cancel, stop, pause, or reduce their own SIP, even when they could not finish it, tree_node is C1 and metric_scope is in_scope. Trying the control and finding that it will not open counts as an attempt. Only a stated intention with no attempt, such as "will it affect me if I stop?", stays none.
These must be tree_node none:
- questions and hypotheticals with no attempt (for example "if I cancel, will debits stop?" or "will it affect me if I stop?")
- advice to other people
- praise
- intent to start ("I want to start a SIP")
- exit and withdrawal complaints with no description of the decision to stop and no attempt to stop
- platform or support complaints with no SIP event

Examples:
1. "Bhai sip band kar diya, market gir raha tha" -> relevant, middle_m4_9, C1, voluntary, paused, metric_scope in_scope, is_sip_instalment_issue no, sip_outcome ended, evidence_quote "sip band kar diya", confidence 0.86
2. "Instalment failed due to insufficient balance, mandate bounce" -> relevant, unclear, C2, involuntary, failed_debit, metric_scope in_scope, is_sip_instalment_issue yes, sip_outcome continuing, evidence_quote "Instalment failed", confidence 0.9
3. "I paused my SIP for 3 months because of expenses" -> relevant, middle_m4_9, C1, voluntary, paused, metric_scope in_scope, is_sip_instalment_issue no, sip_outcome paused_or_reduced, evidence_quote "paused my SIP", confidence 0.9
4. "Nice app, dark mode is smooth" -> is_relevant false, tree_node none, leak_type none, action_taken none, is_sip_instalment_issue no, sip_outcome unclear, confidence 0.95
5. "NAV went down so the value looks red, but the SIP amount was deducted" -> relevant, unclear, B2, none, continued, what_they_check nav, is_sip_instalment_issue no, sip_outcome continuing, evidence_quote "NAV went down", confidence 0.84
6. "Last year I stopped, this month I started the SIP again" -> relevant, restart, E1, voluntary, restarted, metric_scope in_scope, is_sip_instalment_issue no, sip_outcome continuing, evidence_quote "started the SIP again", confidence 0.88
7. "If I cancel, will the next debit still leave my bank?" -> relevant, unclear, none, none, none, is_sip_instalment_issue no, sip_outcome unclear, evidence_quote "If I cancel", confidence 0.9
8. "People should pause their SIP whenever the market is down" -> relevant, unclear, none, none, none, is_sip_instalment_issue no, sip_outcome unclear, evidence_quote "People should pause", confidence 0.9
9. "The SIP page looks clean and the colours are pleasant" -> is_relevant false, tree_node none, leak_type none, action_taken none, is_sip_instalment_issue no, sip_outcome unclear, confidence 0.9
10. "I want to start a SIP once I get my salary" -> relevant, start, none, none, none, is_sip_instalment_issue no, sip_outcome unclear, evidence_quote "I want to start", confidence 0.9
11. "I asked for my money back two weeks ago and it is still not in my account" -> relevant, unclear, none, none, none, metric_scope exit_experience, is_sip_instalment_issue no, sip_outcome unclear, evidence_quote "not in my account", confidence 0.88
12. "Support has not answered my ticket about a chart that will not load" -> is_relevant false, tree_node none, leak_type none, action_taken none, is_sip_instalment_issue no, sip_outcome unclear, confidence 0.9
13. "I opened my SIP settings and tried to cancel it, but the cancel control never loaded" -> relevant, middle_m4_9, C1, voluntary, cancelled, metric_scope in_scope, is_sip_instalment_issue no, sip_outcome continuing, evidence_quote "tried to cancel", confidence 0.9
14. "Will it affect me if I stop?" -> relevant, unclear, none, none, none, metric_scope unclear, is_sip_instalment_issue no, sip_outcome unclear, evidence_quote "if I stop", confidence 0.92
15. "I created the SIP this morning and the first debit has not left my bank" -> relevant, start, A1, involuntary, failed_debit, metric_scope in_scope, is_sip_instalment_issue yes, sip_outcome continuing, evidence_quote "first debit has not", confidence 0.9
16. "This month's instalment on my running SIP is stuck and will not complete" -> relevant, unclear, C2, involuntary, failed_debit, metric_scope in_scope, is_sip_instalment_issue yes, sip_outcome continuing, evidence_quote "instalment on my running SIP", confidence 0.9
17. "The third instalment did not leave the bank" -> relevant, settle_in_m1_3, B1, involuntary, failed_debit, metric_scope in_scope, is_sip_instalment_issue yes, sip_outcome continuing, evidence_quote "third instalment", confidence 0.9
18. "The same SIP has failed four months in a row even with a full balance" -> relevant, middle_m4_9, C2, involuntary, failed_debit, metric_scope in_scope, is_sip_instalment_issue yes, sip_outcome continuing, evidence_quote "failed four months", confidence 0.9
"""

COMPACT_SYSTEM = """You tag public comments about a SIP (a fixed amount invested every month).
Return JSON only. No markdown. No explanation. No keys other than the ones listed.
Use only the comment text. If a detail is not there, use unclear, none, or an empty phrase. Never guess.
Do not name a fund or a stock. Do not tell anyone to buy, sell, stay, or hurry.

Each comment is one object:
{"id":"c1","tree_node":"none","metric_scope":"unclear","sip_outcome":"unclear","is_sip_instalment_issue":"no","leak_type":"none","tenure_hint":"unclear","confusion_point":"","unmet_need":"","workaround":"none","evidence_quote":"","confidence":0.0}

tree_node: A1 | A2 | B1 | B2 | C1 | C2 | C3 | D1 | E1 | none
A1 setup or the first debit only, including a failed first debit.
A2 setup abandoned before the SIP is running.
B1 the 2nd or 3rd instalment.
B2 first statement or first look at value.
C1 pause, cancel, reduce, or redeem, including a failed attempt to do that.
C2 a problem paying or processing an instalment of a SIP that is already set up, including repeated failure when the balance is enough.
C3 the user fixed a failed debit.
D1 still investing around month 12.
E1 restarted after a pause or a failure.
none: no event on the commenter's own SIP.

An attempt to cancel, stop, pause, or reduce their own SIP is C1 and metric_scope in_scope, even if the attempt failed. A stated intention with no attempt, such as "will it affect me if I stop?", is none.
A1 and A2 are only for setting up a SIP or its first debit. A later instalment problem is C2, or B1 when it is clearly the 2nd or 3rd instalment.

metric_scope: in_scope | exit_experience | other_platform_complaint | unclear
sip_outcome: ended | paused_or_reduced | continuing | unclear
ended only if the SIP stopped, was cancelled, or lapsed and they do not say they restarted. A failed debit is continuing or unclear, not ended, unless they say the SIP ended.
paused_or_reduced: paused, reduced, or considering stopping.
is_sip_instalment_issue: yes | no | unclear. yes only when a recurring SIP instalment, autopay, or mandate failed, was missed, or was not debited. A one-time payment, add-money failure, or login/KYC error is no.
leak_type: voluntary | involuntary | none | unclear
tenure_hint: new | under_3_months | 3_to_12_months | over_12_months | restart | unclear
workaround: google | youtube | friends_family | advisor | calculator | other | none
evidence_quote must be an exact substring of that comment, 15 words or fewer.
confusion_point and unmet_need are short phrases, or empty.

Examples:
"Will it affect me if I stop?" -> {"id":"c1","tree_node":"none","metric_scope":"unclear","sip_outcome":"unclear","is_sip_instalment_issue":"no","leak_type":"none","tenure_hint":"unclear","confusion_point":"","unmet_need":"","workaround":"none","evidence_quote":"if I stop","confidence":0.92}
"I tried to cancel my SIP and the button did nothing" -> {"id":"c1","tree_node":"C1","metric_scope":"in_scope","sip_outcome":"continuing","is_sip_instalment_issue":"no","leak_type":"voluntary","tenure_hint":"unclear","confusion_point":"cancel button did nothing","unmet_need":"a cancel button that works","workaround":"none","evidence_quote":"tried to cancel","confidence":0.9}
"The third instalment did not leave the bank" -> {"id":"c1","tree_node":"B1","metric_scope":"in_scope","sip_outcome":"continuing","is_sip_instalment_issue":"yes","leak_type":"involuntary","tenure_hint":"under_3_months","confusion_point":"","unmet_need":"","workaround":"none","evidence_quote":"third instalment","confidence":0.9}
"The same SIP failed four months running even with a full balance" -> {"id":"c1","tree_node":"C2","metric_scope":"in_scope","sip_outcome":"continuing","is_sip_instalment_issue":"yes","leak_type":"involuntary","tenure_hint":"3_to_12_months","confusion_point":"","unmet_need":"","workaround":"none","evidence_quote":"failed four months","confidence":0.9}
"""

RELEVANCE_SYSTEM = """You check whether a public comment is about starting, continuing, pausing, stopping, or failing at a SIP or mutual fund investment.
SIP means a fixed amount invested every month.
Reply with JSON only: {"results":[{"id":"c1","relevant":true}]}
Do not name a fund or a stock.
If the comment is only about the app design, stocks trading, loans, or a greeting, relevant is false.
"""


def load_cache():
    if not config.CACHE_JSON.exists():
        return {"version": PROMPT_VERSION, "relevance": {}, "tags": {}}
    try:
        cache = json.loads(config.CACHE_JSON.read_text())
    except json.JSONDecodeError:
        cache = {}
    if cache.get("version") != PROMPT_VERSION:
        return {"version": PROMPT_VERSION, "relevance": {}, "tags": {}}
    cache.setdefault("relevance", {})
    cache.setdefault("tags", {})
    cache.setdefault("metric_scope", {})
    cache.setdefault("sip_instalment", {})
    return cache


def save_cache(cache):
    config.ensure_data_dir()
    temp = config.CACHE_JSON.with_suffix(".tmp")
    temp.write_text(json.dumps(cache))
    temp.replace(config.CACHE_JSON)


def safe_error(exc):
    text = str(exc)
    text = re.sub(r"hf_\w+", "hf_redacted", text)
    text = re.sub(r"AIza[\w-]+", "AIza_redacted", text)
    text = re.sub(r"gsk_\w+", "gsk_redacted", text)
    text = re.sub(r"nvapi-[\w-]+", "nvapi_redacted", text)
    return text[:400]


def extract_json(text):
    if not text:
        raise ValueError("empty model response")
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    start_obj = cleaned.find("{")
    start_arr = cleaned.find("[")
    starts = [pos for pos in (start_obj, start_arr) if pos >= 0]
    if not starts:
        raise ValueError("no JSON in model response")
    start = min(starts)
    try:
        parsed, _end = json.JSONDecoder().raw_decode(cleaned[start:])
        return parsed
    except json.JSONDecodeError:
        end_obj = cleaned.rfind("}")
        end_arr = cleaned.rfind("]")
        end = max(end_obj, end_arr)
        if end < start:
            raise ValueError("incomplete JSON")
        return json.loads(cleaned[start : end + 1])


def results_of(parsed):
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("results", "items", "comments", "tags"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        if "id" in parsed:
            return [parsed]
    raise ValueError("JSON did not contain a list of results")


class ModelClient:
    def __init__(self, spec):
        self.spec = spec
        self.backend = spec.get("backend", "huggingface")
        self.calls = 0
        self.rate_limits = 0
        self._lock = threading.Lock()
        self._pause_until = 0.0
        self._hf = None
        self._gemini_keys = list(config.GEMINI_KEYS)
        self._gemini_index = 0

    def _wait_for_backoff(self):
        with self._lock:
            pause = self._pause_until
        delay = pause - time.time()
        if delay > 0:
            time.sleep(delay)

    def label(self):
        if self.backend in ("groq", "gemini", "nvidia"):
            return self.backend + ":" + self.spec["model"]
        return self.spec["model"] + ":" + self.spec.get("provider", "auto")

    def complete(self, system, user, max_tokens, temperature=0.1):
        last_error = None
        attempt = 0
        while attempt < 24:
            self._wait_for_backoff()
            try:
                with self._lock:
                    self.calls += 1
                if self.backend == "groq":
                    return self._groq(system, user, max_tokens, temperature)
                if self.backend == "gemini":
                    return self._gemini(system, user, max_tokens, temperature)
                if self.backend == "nvidia":
                    return self._nvidia(system, user, max_tokens, temperature)
                return self._hf_complete(system, user, max_tokens, temperature)
            except Exception as exc:
                last_error = exc
                message = safe_error(exc).lower()
                if self.backend == "nvidia" and any(
                    word in message for word in ("401", "403", "invalid api key", "unauthorized")
                ):
                    raise RuntimeError("NVIDIA rejected the API key. Replace NVIDIA_API_KEY and run this again.")
                if self.backend == "gemini" and any(
                    word in message for word in ("401", "403", "api key not valid", "api_key_invalid")
                ):
                    if self._rotate_gemini():
                        attempt += 1
                        continue
                    raise RuntimeError("Gemini rejected the API key. Replace GEMINI_API_KEY and run this again.")
                if self.backend != "gemini" and any(
                    word in message for word in ("401", "unauthorized", "invalid username", "invalid token")
                ):
                    raise RuntimeError("Hugging Face rejected the token. Replace HF_TOKEN and run this again.")
                if self.backend != "gemini" and any(
                    word in message for word in ("402", "credit", "payment", "insufficient")
                ):
                    raise RuntimeError("Hugging Face credits are used up. " + safe_error(exc))
                attempt += 1
                if attempt >= 24:
                    break
                quota = "429" in message or "quota" in message or "resource_exhausted" in message
                if quota:
                    with self._lock:
                        self.rate_limits += 1
                        self._pause_until = max(self._pause_until, time.time() + 20)
                if self.backend == "nvidia" and quota:
                    wait = 20
                elif self.backend == "gemini" and quota:
                    self._rotate_gemini()
                    wait = 15
                elif any(word in message for word in ("503", "unavailable", "high demand")):
                    wait = min(60, 15 * attempt)
                else:
                    wait = min(40, 8 * attempt)
                print(f"  API wait {wait}s ({safe_error(exc)})")
                time.sleep(wait)
        raise RuntimeError(safe_error(last_error))

    def _rotate_gemini(self):
        if len(self._gemini_keys) < 2:
            return False
        self._gemini_index = (self._gemini_index + 1) % len(self._gemini_keys)
        print("  Switching to the next Gemini key.")
        return True

    def _hf_complete(self, system, user, max_tokens, temperature=0.1):
        if self._hf is None:
            from huggingface_hub import InferenceClient

            self._hf = InferenceClient(token=config.HF_TOKEN, timeout=180)
        model = self.spec["model"]
        provider = self.spec.get("provider")
        model_id = f"{model}:{provider}" if provider else model
        response = self._hf.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    def _groq(self, system, user, max_tokens, temperature=0.1):
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer " + config.GROQ_API_KEY},
            json={
                "model": self.spec["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=180,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Groq HTTP {response.status_code}")
        return response.json()["choices"][0]["message"]["content"]

    def _gemini(self, system, user, max_tokens, temperature=0.1):
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + self.spec["model"]
            + ":generateContent",
            params={"key": self._gemini_keys[self._gemini_index] if self._gemini_keys else config.GEMINI_API_KEY},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
            timeout=180,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Gemini HTTP {response.status_code} {response.text[:240]}")
        data = response.json()
        candidates = data.get("candidates") or []
        parts = ((candidates[0].get("content") or {}).get("parts") if candidates else None) or []
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            reason = candidates[0].get("finishReason") if candidates else "empty"
            raise RuntimeError(f"Gemini returned no text ({reason})")
        return text

    def _nvidia(self, system, user, max_tokens, temperature=0.1):
        response = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={
                "Authorization": "Bearer " + config.NVIDIA_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "model": self.spec["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=180,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"NVIDIA HTTP {response.status_code} {response.text[:240]}")
        data = response.json()
        message = ((data.get("choices") or [{}])[0].get("message") or {})
        text = (message.get("content") or "").strip()
        if not text:
            raise RuntimeError("NVIDIA returned no text")
        return text


def clip(text, limit=450):
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text[:limit]


def format_batch(rows):
    lines = []
    mapping = {}
    for index, row in enumerate(rows, start=1):
        local = f"c{index}"
        mapping[local] = row["id"]
        context = clip(row.get("context", ""), 80)
        prefix = f" (about: {context})" if context else ""
        lines.append(f"{local}{prefix}: {clip(row['text'])}")
    return mapping, "\n".join(lines)


def ask_json(client, system, user, max_tokens, temperature=0.1):
    text = client.complete(system, user, max_tokens, temperature)
    try:
        return results_of(extract_json(text))
    except (ValueError, json.JSONDecodeError):
        text = client.complete(
            system,
            user + "\nReply again with JSON only. No markdown.",
            max_tokens,
            temperature,
        )
        return results_of(extract_json(text))


def probe_score(items):
    by_id = {str(item.get("id", "")).lower(): item for item in items}
    score = 0
    first = by_id.get("c1", {})
    if first.get("is_relevant") is True and first.get("leak_type") == "voluntary":
        score += 1
    if first.get("action_taken") in {"paused", "cancelled"} and first.get("tree_node") in {"C1", "B2"}:
        score += 1
    second = by_id.get("c2", {})
    if (
        second.get("is_relevant") is True
        and second.get("action_taken") == "failed_debit"
        and second.get("leak_type") == "involuntary"
    ):
        score += 1
    third = by_id.get("c3", {})
    if third.get("is_relevant") is False:
        score += 1
    fourth = by_id.get("c4", {})
    if fourth.get("is_relevant") is True and fourth.get("action_taken") != "failed_debit":
        score += 1
    return score


PROBE_USER = """Tag these comments.
c1: Bhai maine sip band kar diya, har mahine paisa kat raha tha aur market gir raha tha
c2: SIP instalment failed due to insufficient balance. Mandate bounce ho gaya and amount was not debited.
c3: Nice app, dark mode is smooth and the UI is fast.
c4: NAV gir gaya is month so portfolio red dikh raha hai, but SIP to kat gaya.
"""


def choose_model():
    if config.NVIDIA_API_KEY:
        spec = {"backend": "nvidia", "model": config.NVIDIA_MODEL, "provider": "nvidia"}
        print(f"Using NVIDIA {config.NVIDIA_MODEL}")
        config.ensure_data_dir()
        config.MODEL_JSON.write_text(json.dumps(spec, indent=2))
        return ModelClient(spec)

    if config.GEMINI_API_KEY and not config.HF_MODEL:
        spec = {"backend": "gemini", "model": config.GEMINI_MODEL, "provider": "google"}
        print(f"Using Gemini {config.GEMINI_MODEL}")
        config.ensure_data_dir()
        config.MODEL_JSON.write_text(json.dumps(spec, indent=2))
        return ModelClient(spec)

    if config.MODEL_JSON.exists() and not config.HF_MODEL:
        saved = json.loads(config.MODEL_JSON.read_text())
        print(f"Using saved model {saved.get('model')} via {saved.get('backend', 'huggingface')}")
        return ModelClient(saved)

    if config.HF_MODEL:
        spec = {
            "backend": "huggingface",
            "model": config.HF_MODEL.split(":")[0],
            "provider": config.HF_PROVIDER or (config.HF_MODEL.split(":")[1] if ":" in config.HF_MODEL else ""),
        }
        print(f"Using HF_MODEL {spec['model']}")
        config.MODEL_JSON.write_text(json.dumps(spec, indent=2))
        return ModelClient(spec)

    if not config.HF_TOKEN:
        raise RuntimeError("No Hugging Face token in the environment.")

    print("Testing free instruct models on 4 comments...")
    ranked = []
    for spec in config.CANDIDATE_MODELS:
        spec = dict(spec)
        spec["backend"] = "huggingface"
        client = ModelClient(spec)
        try:
            items = ask_json(client, TAG_SYSTEM, PROBE_USER, 900)
            score = probe_score(items)
            print(f"  {spec['model']}: score {score}/5")
            ranked.append((score, spec["size"], -spec["input_price"], spec))
        except Exception as exc:
            print(f"  {spec['model']}: failed ({safe_error(exc)})")
    if ranked:
        ranked.sort(reverse=True)
        best = ranked[0][3]
        if ranked[0][0] == 0:
            print("Every model scored 0. Keeping the one that answered so a human can review the tags.")
        config.ensure_data_dir()
        config.MODEL_JSON.write_text(json.dumps(best, indent=2))
        print(f"Chosen model: {best['model']} ({best['provider']})")
        return ModelClient(best)

    if config.GROQ_API_KEY:
        spec = {"backend": "groq", "model": config.GROQ_MODEL, "provider": "groq"}
        print(f"Hugging Face did not answer. Using Groq free model {config.GROQ_MODEL}.")
        config.MODEL_JSON.write_text(json.dumps(spec, indent=2))
        return ModelClient(spec)
    raise RuntimeError(
        "No free Hugging Face model answered, and GROQ_API_KEY is empty. Nothing was tagged."
    )


def one_of(value, options, default):
    if value is None:
        return default, False
    text = str(value).strip()
    for option in options:
        if text.lower() == option.lower():
            return option, True
    return default, False


def as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1"}


def as_confidence(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def lock_quote(quote, source):
    quote = "" if quote is None else str(quote).strip().strip('"')
    if not quote or quote.lower() in {"null", "none"}:
        return "", False
    if quote in source:
        exact = quote
    else:
        match = re.search(re.escape(quote), source, flags=re.I)
        if not match:
            return "", False
        exact = source[match.start() : match.end()]
    words = exact.split()
    if len(words) > 15:
        short = " ".join(words[:15])
        if short in source:
            exact = short
        else:
            return "", False
    return exact, True


def blank_tag(is_relevant=True):
    return {
        "is_relevant": bool(is_relevant),
        "journey_stage": "unclear",
        "tree_node": "none",
        "leak_type": "unclear",
        "action_taken": "none",
        "trigger": "",
        "confusion_point": "",
        "what_they_check": "unclear",
        "workaround_outside_app": "none",
        "income_type": "unclear",
        "age_hint": "unclear",
        "influenced_by": "unclear",
        "emotion": "neutral",
        "unmet_need": "",
        "evidence_quote": "",
        "confidence": 0.0,
        "metric_scope": "",
        "is_sip_instalment_issue": "",
        "sip_outcome": "",
        "status": "needs_review",
    }


def validate_tag(raw, source_text, sebi_rows, row_id):
    tag = blank_tag()
    if not isinstance(raw, dict):
        return tag
    tag["is_relevant"] = as_bool(raw.get("is_relevant", True))
    valid = True
    tag["journey_stage"], ok = one_of(raw.get("journey_stage"), config.JOURNEY_STAGES, "unclear")
    valid = valid and ok
    tag["tree_node"], ok = one_of(raw.get("tree_node"), config.TREE_NODES, "none")
    valid = valid and ok
    tag["leak_type"], ok = one_of(raw.get("leak_type"), config.LEAK_TYPES, "unclear")
    valid = valid and ok
    tag["action_taken"], ok = one_of(raw.get("action_taken"), config.ACTIONS, "none")
    valid = valid and ok
    tag["what_they_check"], ok = one_of(raw.get("what_they_check"), config.CHECKS, "unclear")
    valid = valid and ok
    tag["workaround_outside_app"], ok = one_of(
        raw.get("workaround_outside_app"), config.WORKAROUNDS, "none"
    )
    valid = valid and ok
    tag["income_type"], _ok = one_of(raw.get("income_type"), config.INCOME_TYPES, "unclear")
    tag["age_hint"], _ok = one_of(raw.get("age_hint"), config.AGE_HINTS, "unclear")
    tag["influenced_by"], _ok = one_of(raw.get("influenced_by"), config.INFLUENCES, "unclear")
    tag["emotion"], _ok = one_of(raw.get("emotion"), config.EMOTIONS, "neutral")
    tag["metric_scope"], _ok = one_of(raw.get("metric_scope"), config.METRIC_SCOPES, "")
    tag["is_sip_instalment_issue"], sip_ok = one_of(
        raw.get("is_sip_instalment_issue"), config.SIP_INSTALMENT_VALUES, ""
    )
    tag["sip_outcome"], outcome_ok = one_of(raw.get("sip_outcome"), SIP_OUTCOMES, "")
    if not sip_ok or not outcome_ok:
        valid = False

    for field in ("trigger", "confusion_point", "unmet_need"):
        value = raw.get(field)
        if value is None or str(value).strip().lower() in {"null", "none"}:
            tag[field] = ""
            continue
        cleaned, changed = config.redact_generated(value, source_text)
        tag[field] = "" if cleaned is None else str(cleaned)[:240]
        if changed:
            sebi_rows.append({"row_id": row_id, "field": field, "action": "replaced"})

    quote, quote_ok = lock_quote(raw.get("evidence_quote"), source_text)
    tag["evidence_quote"] = quote
    tag["confidence"] = as_confidence(raw.get("confidence"))
    if not valid or not quote_ok or tag["confidence"] < config.CONFIDENCE_MIN:
        tag["status"] = "needs_review"
    else:
        tag["status"] = "ok"
    if not tag["is_relevant"] and tag["confidence"] >= config.CONFIDENCE_MIN and valid:
        tag["status"] = "dropped"
    return tag


def relevance_pass(client, df, cache):
    pending = []
    known = []
    for _, row in df.iterrows():
        key = row["id"]
        if key in cache["relevance"]:
            known.append(key)
        else:
            pending.append(row)
    print(f"Relevance: {len(known)} cached, {len(pending)} to check")
    dropped_ids = []
    rounds = 0
    while pending and rounds < 6:
        still = []
        for start in range(0, len(pending), RELEVANCE_BATCH):
            batch = pending[start : start + RELEVANCE_BATCH]
            mapping, body = format_batch(batch)
            user = (
                "Is this person talking about starting, continuing, pausing, stopping, "
                "or failing at a SIP or mutual fund investment?\n" + body
            )
            try:
                items = ask_json(client, RELEVANCE_SYSTEM, user, 700)
            except Exception as exc:
                message = safe_error(exc).lower()
                if any(word in message for word in ("429", "503", "quota", "unavailable", "timeout")):
                    print("  Relevance batch hit a limit. It stays untagged and will be tried again.")
                    still.extend(batch)
                    continue
                print(f"  Relevance batch failed ({safe_error(exc)}). Those rows will be tagged and marked for review.")
                for row in batch:
                    cache["relevance"][row["id"]] = True
                save_cache(cache)
                continue
            returned = {}
            for item in items:
                if not isinstance(item, dict):
                    continue
                local = str(item.get("id", "")).lower()
                if local in mapping and "relevant" in item:
                    returned[mapping[local]] = as_bool(item.get("relevant"))
            for row in batch:
                if row["id"] in returned:
                    cache["relevance"][row["id"]] = returned[row["id"]]
                    if not returned[row["id"]]:
                        dropped_ids.append(row["id"])
                else:
                    cache["relevance"][row["id"]] = True
            save_cache(cache)
            done = len(cache["relevance"])
            print(f"  Relevance cached {done}")
            time.sleep(1.2)
        pending = still
        rounds += 1
        if pending:
            print(f"  {len(pending)} comments are waiting on the model. Pausing 90s, then retrying.")
            time.sleep(90)
    kept = df[df["id"].map(lambda row_id: cache["relevance"].get(row_id, False))].copy()
    print(f"After relevance: {len(kept)} kept, {len(df) - len(kept)} dropped")
    return kept, dropped_ids


def tag_pass(client, df, cache):
    sebi_rows = []
    pending = [row for _, row in df.iterrows() if row["id"] not in cache["tags"]]
    print(f"Tagging: {len(df) - len(pending)} cached, {len(pending)} to tag")
    for start in range(0, len(pending), TAG_BATCH):
        batch = pending[start : start + TAG_BATCH]
        mapping, body = format_batch(batch)
        user = (
            "Tag each comment. evidence_quote must be copied from that comment.\n" + body
        )
        parsed = {}
        try:
            items = ask_json(client, TAG_SYSTEM, user, 1600)
            for item in items:
                if isinstance(item, dict):
                    local = str(item.get("id", "")).lower()
                    if local in mapping:
                        parsed[mapping[local]] = item
        except Exception as exc:
            print(f"  Tag batch failed ({safe_error(exc)}). Marked for review.")
        for row in batch:
            raw = parsed.get(row["id"])
            tag = validate_tag(raw, row["text"], sebi_rows, row["id"]) if raw else blank_tag()
            cache["tags"][row["id"]] = tag
        save_cache(cache)
        done = min(start + TAG_BATCH, len(pending))
        print(f"  Tagged {done}/{len(pending)}")
        time.sleep(0.6)
    if sebi_rows:
        previous = config.read_csv(config.SEBI_LOG)
        config.write_csv(pd.concat([previous, pd.DataFrame(sebi_rows)], ignore_index=True), config.SEBI_LOG)
        print(f"Output filter replaced {len(sebi_rows)} fields")
    return cache


def attach_tags(df, cache):
    records = []
    for _, row in df.iterrows():
        tag = cache["tags"].get(row["id"]) or blank_tag()
        item = row.to_dict()
        item.update(tag)
        item["is_relevant"] = bool(tag.get("is_relevant"))
        records.append(item)
    return pd.DataFrame(records)


def balance(df):
    """Keep at most 3,000 relevant rows, aiming for a Groww and source mix."""
    work = df[df["status"] != "dropped"].copy()
    work["confidence"] = pd.to_numeric(work["confidence"], errors="coerce").fillna(0)
    work["keyword_count"] = pd.to_numeric(work["keyword_count"], errors="coerce").fillna(0)
    work = work.sort_values(["confidence", "keyword_count"], ascending=False)

    ok = work[work["status"] == "ok"]
    review = work[work["status"] != "ok"]
    target = min(config.FINAL_CAP, len(ok)) if len(ok) else 0
    if target == 0:
        return review.head(config.FINAL_CAP).copy(), 0

    max_source = max(1, int(target * config.SOURCE_SHARE_MAX))
    min_groww = int(target * config.GROWW_SHARE_MIN)
    chosen = []
    chosen_ids = set()
    source_counts = {}

    def take(frame, limit, respect_source_cap):
        for _, row in frame.iterrows():
            if len(chosen) >= limit:
                break
            if row["id"] in chosen_ids:
                continue
            source = row.get("source") or "unknown"
            if respect_source_cap and source_counts.get(source, 0) >= max_source:
                continue
            chosen.append(row.to_dict())
            chosen_ids.add(row["id"])
            source_counts[source] = source_counts.get(source, 0) + 1

    groww_rows = ok[ok["app"] == "Groww"]
    take(groww_rows, min_groww, respect_source_cap=True)
    take(ok, target, respect_source_cap=True)
    if len(chosen) < target:
        take(ok, target, respect_source_cap=False)
    final = pd.DataFrame(chosen)
    room = config.FINAL_CAP - len(final)
    if room > 0 and len(review):
        extra = review.head(room)
        final = pd.concat([final, extra], ignore_index=True)
    groww_share = 0 if final.empty else (final["app"] == "Groww").mean()
    print(f"Final rows: {len(final)}")
    print(f"Groww share: {groww_share:.0%}")
    if not final.empty:
        print("Source mix:")
        print(final["source"].value_counts(normalize=True).round(2).to_string())
    if groww_share < config.GROWW_SHARE_MIN:
        print("Groww is under 40% of this set. There were not enough Groww comments that passed the filters.")
    return final, int((final["status"] == "ok").sum()) if len(final) else 0


def tag_one(text):
    """Tag a single pasted comment. The text is not written to disk."""
    if config.NVIDIA_API_KEY:
        spec = {"backend": "nvidia", "model": config.NVIDIA_MODEL, "provider": "nvidia"}
    elif config.GEMINI_API_KEY and not config.HF_MODEL:
        spec = {"backend": "gemini", "model": config.GEMINI_MODEL, "provider": "google"}
    elif config.MODEL_JSON.exists():
        spec = json.loads(config.MODEL_JSON.read_text())
    elif config.HF_MODEL:
        spec = {
            "backend": "huggingface",
            "model": config.HF_MODEL.split(":")[0],
            "provider": config.HF_PROVIDER,
        }
    else:
        spec = dict(config.CANDIDATE_MODELS[0])
        spec["backend"] = "huggingface"
    client = ModelClient(spec)
    user = "Tag this comment. evidence_quote must be copied from it.\nc1: " + clip(text, 800)
    try:
        items = ask_json(client, TAG_SYSTEM, user, 700)
    except Exception:
        tag = blank_tag()
        tag["notice"] = "The model did not return a tag."
        return tag
    raw = items[0] if items else None
    tag = validate_tag(raw, text, [], "try-it")
    return tag


SCOPE_BATCH = 12
SCOPE_SYSTEM = """You decide whether a public comment is about continuing a SIP, or about something else.
SIP means a fixed amount invested every month.
Reply with JSON only: {"results":[{"id":"c1","metric_scope":"in_scope"}]}
Do not name a fund or a stock. Do not tell anyone to buy, sell, stay, or hurry.

metric_scope is one of: in_scope | exit_experience | other_platform_complaint | unclear
- in_scope: the comment is about starting, continuing, pausing, reducing, failing, restarting, or understanding a SIP instalment while the person is still investing or deciding whether to continue.
- exit_experience: the person has already decided to leave and the comment is about the exit itself (redemption speed, withdrawal delay, account closure, post-exit support).
- other_platform_complaint: complaints about fees, paid plans, reports, KYC, UI bugs, or other features that do not mention a SIP instalment, a pause, or a stop.
- unclear: cannot tell.
"""


def scope_pass(client, df, cache):
    """Label metric_scope for every row. Cached rows are not sent again."""
    cache.setdefault("metric_scope", {})
    cache.setdefault("tags", {})
    pending = []
    for _, row in df.iterrows():
        if row["id"] not in cache["metric_scope"]:
            pending.append(row)
    print(f"Scope: {len(df) - len(pending)} cached, {len(pending)} to label")
    rounds = 0
    while pending and rounds < 8:
        still = []
        for start in range(0, len(pending), SCOPE_BATCH):
            batch = pending[start : start + SCOPE_BATCH]
            mapping, body = format_batch(batch)
            user = "Set metric_scope for each comment.\n" + body
            try:
                items = ask_json(client, SCOPE_SYSTEM, user, 700)
            except Exception as exc:
                message = safe_error(exc).lower()
                print(f"  Scope batch failed ({safe_error(exc)}). It stays unlabelled.")
                still.extend(batch)
                if any(word in message for word in ("429", "503", "quota", "unavailable", "timeout")):
                    time.sleep(20)
                continue
            returned = {}
            for item in items:
                if not isinstance(item, dict):
                    continue
                local = str(item.get("id", "")).lower()
                scope, ok = one_of(item.get("metric_scope"), config.METRIC_SCOPES, "")
                if local in mapping and ok:
                    returned[mapping[local]] = scope
            for row in batch:
                if row["id"] not in returned:
                    still.append(row)
                    continue
                scope = returned[row["id"]]
                cache["metric_scope"][row["id"]] = scope
                if row["id"] in cache["tags"] and isinstance(cache["tags"][row["id"]], dict):
                    cache["tags"][row["id"]]["metric_scope"] = scope
            save_cache(cache)
            print(f"  Scope cached {len(cache['metric_scope'])}")
            time.sleep(1.2)
        pending = still
        rounds += 1
        if pending:
            print(f"  {len(pending)} comments still need a scope. Pausing 30s.")
            time.sleep(30)
    labelled = df["id"].map(lambda row_id: cache["metric_scope"].get(row_id, ""))
    print("Scope counts:")
    print(labelled.replace("", "(missing)").value_counts().to_string())
    return labelled


def apply_scope_to_final(cache):
    """Write metric_scope onto final.csv without dropping rows. Unclear rows join the review list."""
    import csv
    from datetime import date
    import importlib.util

    final = config.read_csv(config.FINAL_CSV)
    if final.empty:
        raise RuntimeError("No final.csv yet.")
    spec = importlib.util.spec_from_file_location("score_mod", config.ROOT / "4_score.py")
    score = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(score)

    def top_line(frame):
        ranking = score.build_ranking(frame)
        if ranking.empty or "slice_type" not in ranking.columns:
            return "no ranking"
        overall = ranking[ranking["slice_type"] == "all"].sort_values("score", ascending=False).head(3)
        bits = [f"{row.tree_node} n={int(row.n)} score={row.score}" for row in overall.itertuples()]
        return f"confident {len(score.usable(frame))}; top " + "; ".join(bits)

    before = top_line(final)
    final["metric_scope"] = final["id"].map(lambda row_id: cache["metric_scope"].get(row_id, ""))
    missing = int((final["metric_scope"] == "").sum())
    config.write_csv(final, config.FINAL_CSV)

    unclear = final[final["metric_scope"] == "unclear"]
    review = config.read_csv(config.NEEDS_REVIEW_CSV)
    if len(unclear):
        if review.empty:
            extra = unclear
        else:
            known = set(review["id"].astype(str)) if "id" in review.columns else set()
            extra = unclear[~unclear["id"].astype(str).isin(known)]
        if len(extra):
            config.write_csv(pd.concat([review, extra], ignore_index=True), config.NEEDS_REVIEW_CSV)
            print(f"Added {len(extra)} unclear rows to the needs-review list.")

    in_scope = final[final["metric_scope"] == "in_scope"]
    after_counts = final["metric_scope"].replace("", "(missing)").value_counts().to_dict()
    after = top_line(in_scope) + ". counts " + json.dumps({str(k): int(v) for k, v in after_counts.items()})
    if missing:
        after += f". {missing} rows still missing a scope."
    log_path = config.DATA_DIR / "changes_log.csv"
    already = log_path.read_text() if log_path.exists() else ""
    if missing == 0 and "Added metric_scope" not in already:
        with log_path.open("a", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["date", "change", "reason", "rows_affected", "before_summary", "after_summary"],
            )
            writer.writerow(
                {
                    "date": date.today().isoformat(),
                    "change": "Added metric_scope on every final.csv row",
                    "reason": "Separate continuation comments from exit and other complaints. This rule was added after the first ranking.",
                    "rows_affected": int(len(final)),
                    "before_summary": before,
                    "after_summary": after,
                }
            )
    elif missing:
        print(f"Not logging yet. {missing} rows still have no scope.")
    print("Before ranking:", before)
    print("After in-scope ranking:", after)
    return final


INSTALMENT_BATCH = 12
INSTALMENT_SYSTEM = """You decide whether a public comment is about a recurring SIP instalment failing.
SIP means a fixed amount invested every month.
Reply with JSON only: {"results":[{"id":"c1","is_sip_instalment_issue":"yes"}]}
Do not name a fund or a stock. Do not tell anyone to buy, sell, stay, or hurry.

Question: Does this comment clearly say a recurring SIP instalment, autopay, or mandate failed, was missed, or was not debited? A one-time payment, add-money failure, or login/KYC error is no.

is_sip_instalment_issue is one of: yes | no | unclear
- yes: the comment clearly says a recurring SIP instalment, autopay, or mandate failed, was missed, or was not debited.
- no: a one-time payment, add-money failure, login, or KYC error, or the comment does not clearly say a recurring instalment failed.
- unclear: cannot tell.
"""


def instalment_pass(client, df, cache):
    """Label is_sip_instalment_issue for C1, C2, C3, A1, and B1. Cached rows are not sent again."""
    cache.setdefault("sip_instalment", {})
    cache.setdefault("tags", {})
    nodes = set(config.SIP_INSTALMENT_NODES)
    target = df[df["tree_node"].astype(str).isin(nodes)]
    pending = []
    for _, row in target.iterrows():
        if row["id"] not in cache["sip_instalment"]:
            pending.append(row)
    print(f"Instalment check: {len(target) - len(pending)} cached, {len(pending)} to label")
    rounds = 0
    while pending and rounds < 8:
        still = []
        for start in range(0, len(pending), INSTALMENT_BATCH):
            batch = pending[start : start + INSTALMENT_BATCH]
            mapping, body = format_batch(batch)
            user = "Set is_sip_instalment_issue for each comment.\n" + body
            try:
                items = ask_json(client, INSTALMENT_SYSTEM, user, 700)
            except Exception as exc:
                message = safe_error(exc).lower()
                print(f"  Instalment batch failed ({safe_error(exc)}). It stays unlabelled.")
                still.extend(batch)
                if any(word in message for word in ("429", "503", "quota", "unavailable", "timeout")):
                    time.sleep(20)
                continue
            returned = {}
            for item in items:
                if not isinstance(item, dict):
                    continue
                local = str(item.get("id", "")).lower()
                value, ok = one_of(item.get("is_sip_instalment_issue"), config.SIP_INSTALMENT_VALUES, "")
                if local in mapping and ok:
                    returned[mapping[local]] = value
            for row in batch:
                if row["id"] not in returned:
                    still.append(row)
                    continue
                value = returned[row["id"]]
                cache["sip_instalment"][row["id"]] = value
                if row["id"] in cache["tags"] and isinstance(cache["tags"][row["id"]], dict):
                    cache["tags"][row["id"]]["is_sip_instalment_issue"] = value
            save_cache(cache)
            print(f"  Instalment cached {len(cache['sip_instalment'])}")
            time.sleep(1.2)
        pending = still
        rounds += 1
        if pending:
            print(f"  {len(pending)} comments still need an instalment check. Pausing 30s.")
            time.sleep(30)
    labelled = target["id"].map(lambda row_id: cache["sip_instalment"].get(row_id, ""))
    print("Instalment counts:")
    print(labelled.replace("", "(missing)").value_counts().to_string())
    return labelled


def apply_instalment_to_final(cache):
    """Write is_sip_instalment_issue onto final.csv. C2 rows marked no stay in the file."""
    import csv
    from datetime import date
    import importlib.util

    final = config.read_csv(config.FINAL_CSV)
    if final.empty:
        raise RuntimeError("No final.csv yet.")
    spec = importlib.util.spec_from_file_location("score_mod", config.ROOT / "4_score.py")
    score = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(score)
    nodes = set(config.SIP_INSTALMENT_NODES)
    final["is_sip_instalment_issue"] = final["id"].map(lambda row_id: cache.get("sip_instalment", {}).get(row_id, ""))
    target = final["tree_node"].astype(str).isin(nodes)
    missing = int(((final["is_sip_instalment_issue"] == "") & target).sum())
    config.write_csv(final, config.FINAL_CSV)

    def c2_line(frame):
        ranking = score.build_ranking(frame)
        usable_n = len(score.usable(frame))
        if ranking.empty or "slice_type" not in ranking.columns:
            return f"confident {usable_n}; C2 n=0"
        overall = ranking[(ranking["slice_type"] == "all") & (ranking["tree_node"] == "C2")]
        if overall.empty:
            return f"confident {usable_n}; C2 n=0"
        row = overall.iloc[0]
        return f"confident {usable_n}; C2 n={int(row.n)} score={row.score}"

    in_scope = final[final["metric_scope"].astype(str) == "in_scope"] if "metric_scope" in final.columns else final
    before = c2_line(in_scope)
    drop = in_scope["tree_node"].astype(str).eq("C2") & in_scope["is_sip_instalment_issue"].astype(str).eq("no")
    after_frame = in_scope.loc[~drop]
    c2 = score.usable(in_scope)
    c2 = c2[c2["tree_node"].astype(str).eq("C2")] if not c2.empty else c2
    values = c2["is_sip_instalment_issue"].astype(str) if not c2.empty and "is_sip_instalment_issue" in c2.columns else []
    yes = int((values == "yes").sum()) if len(c2) else 0
    no = int((values == "no").sum()) if len(c2) else 0
    unclear = int((values == "unclear").sum()) if len(c2) else 0
    after = c2_line(after_frame) + f". in-scope confident C2 yes {yes}, no {no}, unclear {unclear}. {yes} of {len(c2)} are clearly about a recurring SIP instalment."
    if missing:
        after += f" {missing} target rows still missing a label."
    log_path = config.DATA_DIR / "changes_log.csv"
    already = log_path.read_text() if log_path.exists() else ""
    if missing == 0 and "Checked recurring SIP instalment" not in already:
        with log_path.open("a", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["date", "change", "reason", "rows_affected", "before_summary", "after_summary"],
            )
            writer.writerow(
                {
                    "date": date.today().isoformat(),
                    "change": "Checked recurring SIP instalment on C1, C2, C3, A1, and B1",
                    "reason": "A C2 tag was counting one-time payments, add-money failures, and KYC errors as failed SIP instalments. Comments marked no stay in the file and are left out of the in-scope C2 count.",
                    "rows_affected": int(target.sum()),
                    "before_summary": before,
                    "after_summary": after,
                }
            )
    elif missing:
        print(f"Not logging yet. {missing} target rows still have no instalment label.")
    print("Before in-scope C2:", before)
    print("After in-scope C2:", after)
    return final


def retag_audit_sample(client):
    """Retag the 105 audit comments with the current prompt. Does not write final.csv or the tag cache."""
    import csv
    from datetime import date

    import importlib.util

    spec = importlib.util.spec_from_file_location("eval_mod", config.ROOT / "5_evaluate.py")
    evaluate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluate)

    sample = config.read_csv(evaluate.AUDIT_SAMPLE)
    answers = config.read_csv(evaluate.AUDIT_ANSWERS)
    if sample.empty or answers.empty:
        raise RuntimeError("Audit files are missing.")
    by_id = answers.set_index("id")
    records = []
    for position, row in enumerate(sample.itertuples(index=False), start=1):
        answer = by_id.loc[row.id]
        records.append(
            {
                "id": row.id,
                "text": row.text,
                "position": position,
                "split": "tune" if position % 2 else "test",
                "human_tree_node": row.human_tree_node,
                "tree_node": answer["tree_node"],
                "metric_scope": answer["metric_scope"],
            }
        )
    frame = pd.DataFrame(records)
    audit_temperature = 0
    print(f"Temperature for this audit retag: {audit_temperature}")
    print("Retagging 105 audit rows only. The saved tags for the full file are not changed.")
    print(f"Tune set (odd positions): {(frame['split']=='tune').sum()}. Test set (even positions): {(frame['split']=='test').sum()}.")
    cache_path = config.CACHE_JSON
    cache_stamp = (cache_path.stat().st_mtime, cache_path.stat().st_size) if cache_path.exists() else None
    pending = [row for _, row in frame.iterrows()]
    parsed = {}
    rounds = 0
    while pending and rounds < 4:
        still = []
        for start in range(0, len(pending), TAG_BATCH):
            batch = pending[start : start + TAG_BATCH]
            mapping, body = format_batch(batch)
            user = "Tag each comment. evidence_quote must be copied from that comment.\n" + body
            try:
                items = ask_json(client, TAG_SYSTEM, user, 1600, audit_temperature)
            except Exception as exc:
                print(f"  Audit retag batch failed ({safe_error(exc)}). It will be tried again.")
                still.extend(batch)
                time.sleep(20)
                continue
            returned = {}
            for item in items:
                if isinstance(item, dict):
                    local = str(item.get("id", "")).lower()
                    if local in mapping:
                        returned[mapping[local]] = item
            for row in batch:
                raw = returned.get(row["id"])
                if not raw:
                    still.append(row)
                    continue
                tag = validate_tag(raw, row["text"], [], row["id"])
                sip = raw.get("is_sip_instalment_issue")
                tag["sip_instalment"] = "" if sip is None or str(sip).strip().lower() in {"", "null", "none"} else str(sip).strip()
                parsed[row["id"]] = tag
            print(f"  Retagged {len(parsed)} of {len(frame)}")
            time.sleep(0.6)
        pending = still
        rounds += 1
    if pending:
        print(f"{len(pending)} audit rows did not return a tag. They are left out of the after counts.")
    frame["new_tree_node"] = frame["id"].map(lambda row_id: (parsed.get(row_id) or {}).get("tree_node", ""))
    frame["new_metric_scope"] = frame["id"].map(lambda row_id: (parsed.get(row_id) or {}).get("metric_scope", ""))
    frame["new_confidence"] = frame["id"].map(lambda row_id: (parsed.get(row_id) or {}).get("confidence", ""))
    frame["new_sip_instalment"] = frame["id"].map(lambda row_id: (parsed.get(row_id) or {}).get("sip_instalment", ""))
    frame["new_needs_review"] = frame["id"].map(
        lambda row_id: "yes" if (parsed.get(row_id) or {}).get("status") == "needs_review" else "no"
    )
    tagged = frame[frame["id"].isin(parsed)].copy()
    retag_path = config.DATA_DIR / "audit_retag.csv"
    config.write_csv(
        tagged[
            [
                "id",
                "new_tree_node",
                "new_metric_scope",
                "new_sip_instalment",
                "new_confidence",
                "new_needs_review",
            ]
        ].rename(
            columns={
                "new_tree_node": "new tree_node",
                "new_metric_scope": "new metric_scope",
                "new_sip_instalment": "new sip_instalment value",
                "new_confidence": "new confidence",
                "new_needs_review": "new needs_review flag",
            }
        ),
        retag_path,
    )
    print(f"Wrote {len(tagged)} rows to {retag_path.name}. cache.json was not written.")
    if cache_path.exists():
        now = (cache_path.stat().st_mtime, cache_path.stat().st_size)
        print("cache.json unchanged" if now == cache_stamp else "WARNING cache.json changed")

    def report(part, label):
        print(f"\n{label}: {len(part)} rows")
        evaluate._print_counts(
            "Before, model tree_node",
            evaluate._agreement_counts(part, lambda row: row.get("tree_node", "")),
        )
        evaluate._print_counts(
            "After, model tree_node",
            evaluate._agreement_counts(part, lambda row: row.get("new_tree_node", "")),
        )
        evaluate._print_counts(
            "Before, pipeline stage. This is the pipeline's real output.",
            evaluate._agreement_counts(part, lambda row: evaluate.pipeline_node(row.get("tree_node", ""), row.get("metric_scope", ""))),
        )
        evaluate._print_counts(
            "After, pipeline stage. This is the pipeline's real output.",
            evaluate._agreement_counts(part, lambda row: evaluate.pipeline_node(row.get("new_tree_node", ""), row.get("new_metric_scope", ""))),
        )

    tune = tagged[tagged["split"] == "tune"]
    test = tagged[tagged["split"] == "test"]
    report(tune, "Tune set")
    report(test, "Test set")

    def pack(part, node_col, scope_col=None):
        if scope_col:
            counts = evaluate._agreement_counts(
                part, lambda row: evaluate.pipeline_node(row.get(node_col, ""), row.get(scope_col, ""))
            )
        else:
            counts = evaluate._agreement_counts(part, lambda row: row.get(node_col, ""))
        return (
            f"stage {counts['stage']} of {counts['n']}; "
            f"exact {counts['exact']} of {counts['n']}; "
            f"none {counts['none']} of {counts['none_n']}; "
            f"C {counts['c']} of {counts['c_n']}"
        )

    earlier = {
        "tune": {"stage": 40, "exact": 38, "none": 28, "c": 9, "n": 53, "none_n": 35, "c_n": 13},
        "test": {"stage": 40, "exact": 37, "none": 28, "c": 10, "n": 52, "none_n": 35, "c_n": 14},
    }
    diffs = []
    for split_name, part in (("tune", tune), ("test", test)):
        got = evaluate._agreement_counts(part, lambda row: row.get("new_tree_node", ""))
        was = earlier[split_name]
        for key, label in (("stage", "stage"), ("exact", "exact"), ("none", "none"), ("c", "stage C")):
            if got[key] != was[key] or got["n" if key in {"stage", "exact"} else ("none_n" if key == "none" else "c_n")] != was["n" if key in {"stage", "exact"} else ("none_n" if key == "none" else "c_n")]:
                denom = got["n" if key in {"stage", "exact"} else ("none_n" if key == "none" else "c_n")]
                old_denom = was["n" if key in {"stage", "exact"} else ("none_n" if key == "none" else "c_n")]
                diffs.append(
                    f"{split_name} {label} was {was[key]} of {old_denom}, now {got[key]} of {denom} ({got[key] - was[key]:+d})"
                )
    if diffs:
        print("\nNumbers that differ from the earlier report:")
        for line in diffs:
            print(" ", line)
    else:
        print("\nNo number differs from the earlier report.")
    before_summary = (
        f"Earlier retag at temperature 0.1. Tune after stage 40 of 53; exact 38 of 53; none 28 of 35; C 9 of 13. "
        f"Test after stage 40 of 52; exact 37 of 52; none 28 of 35; C 10 of 14."
    )
    after_summary = (
        f"Rerun at temperature {audit_temperature}. Tune after {pack(tune, 'new_tree_node')}. "
        f"Test after {pack(test, 'new_tree_node')}. "
        + ("Differences: " + "; ".join(diffs) + ". " if diffs else "No difference from the earlier report. ")
        + "Saved to audit_retag.csv. cache.json was not changed. Full 2477 rows were not retagged."
    )
    log_path = config.DATA_DIR / "changes_log.csv"
    with log_path.open("a", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "change", "reason", "rows_affected", "before_summary", "after_summary"],
        )
        writer.writerow(
            {
                "date": date.today().isoformat(),
                "change": "Reran the 105 audit rows at temperature 0 and saved audit_retag.csv",
                "reason": "The first retag was not stored row by row. This rerun uses the same prompt, writes only audit_retag.csv, and leaves cache.json and the human labels unchanged.",
                "rows_affected": int(len(tagged)),
                "before_summary": before_summary,
                "after_summary": after_summary,
            }
        )
    print("Logged the rerun. Saved tags for the other rows were not changed.")
    return tagged


def write_rows(df, path):
    """Write a CSV and replace the destination only after the write finishes."""
    temp = path.with_suffix(path.suffix + ".tmp")
    config.write_csv(df, temp)
    temp.replace(path)


def cache_stamp():
    path = config.CACHE_JSON
    if not path.exists():
        return None
    stat = path.stat()
    return (stat.st_mtime, stat.st_size)


def count_values(series, keys):
    got = series.fillna("").astype(str).str.strip().value_counts()
    parts = [f"{key} {int(got.get(key, 0))}" for key in keys]
    extra = int(sum(int(got.get(key, 0)) for key in got.index if key not in keys and key != ""))
    missing = int(got.get("", 0))
    if extra:
        parts.append(f"other {extra}")
    if missing:
        parts.append(f"missing {missing}")
    return "; ".join(parts)


def tag_rows_at_temperature(client, rows, temperature):
    """Tag these rows with the current prompt. Does not read or write data/cache.json."""
    pending = list(rows)
    parsed = {}
    rounds = 0
    while pending and rounds < 4:
        still = []
        for start in range(0, len(pending), TAG_BATCH):
            batch = pending[start : start + TAG_BATCH]
            mapping, body = format_batch(batch)
            user = "Tag each comment. evidence_quote must be copied from that comment.\n" + body
            try:
                items = ask_json(client, TAG_SYSTEM, user, RETAG_MAX_TOKENS, temperature)
            except Exception as exc:
                print(f"  Retag batch failed ({safe_error(exc)}). It will be tried again.", flush=True)
                still.extend(batch)
                time.sleep(20)
                continue
            returned = {}
            for item in items:
                if isinstance(item, dict):
                    local = str(item.get("id", "")).lower()
                    if local in mapping:
                        returned[mapping[local]] = item
            for row in batch:
                raw = returned.get(row["id"])
                if not raw:
                    still.append(row)
                    continue
                parsed[row["id"]] = validate_tag(raw, row["text"], [], row["id"])
            print(f"  Tagged {len(parsed)}", flush=True)
            time.sleep(0.6)
        pending = still
        rounds += 1
        if pending:
            print(f"  {len(pending)} rows still need a tag. Pausing 30s.", flush=True)
            time.sleep(30)
    for row in pending:
        parsed[row["id"]] = blank_tag()
    return parsed


def sanity_audit_retag(client):
    """One post-hoc pass on the 105 audit rows. Not an independent test. Does not write audit labels or cache.json."""
    sample = config.read_csv(config.DATA_DIR / "audit_sample.csv")
    if sample.empty:
        raise RuntimeError("Audit sample is missing.")
    print("post-hoc, not an independent test", flush=True)
    print(f"Temperature: {RETAG_TEMPERATURE}", flush=True)
    print("This pass does not score agreement and does not write the audit labels or cache.json.", flush=True)
    stamp = cache_stamp()
    rows = [row for _, row in sample.iterrows()]
    parsed = tag_rows_at_temperature(client, rows, RETAG_TEMPERATURE)
    records = []
    for row in rows:
        tag = parsed.get(row["id"]) or blank_tag()
        item = {"id": row["id"], "check": "post-hoc, not an independent test"}
        item.update(tag)
        records.append(item)
    out = pd.DataFrame(records)
    path = config.DATA_DIR / "audit_retag_v2.csv"
    config.write_csv(out, path)
    print(f"Wrote {len(out)} rows to {path.name}.", flush=True)
    print("Tree nodes: " + count_values(out["tree_node"], config.TREE_NODES), flush=True)
    print("Scope: " + count_values(out["metric_scope"], config.METRIC_SCOPES), flush=True)
    print("sip_outcome: " + count_values(out["sip_outcome"], SIP_OUTCOMES), flush=True)
    print(
        "is_sip_instalment_issue: " + count_values(out["is_sip_instalment_issue"], config.SIP_INSTALMENT_VALUES),
        flush=True,
    )
    filled_outcome = int(out["sip_outcome"].astype(str).str.strip().ne("").sum())
    filled_sip = int(out["is_sip_instalment_issue"].astype(str).str.strip().ne("").sum())
    print(f"Filled sip_outcome {filled_outcome} of {len(out)}. Filled is_sip_instalment_issue {filled_sip} of {len(out)}.", flush=True)
    now = cache_stamp()
    print("cache.json unchanged" if now == stamp else "WARNING cache.json changed", flush=True)
    if now != stamp:
        raise RuntimeError("cache.json changed during the audit sanity check.")
    import csv
    from datetime import date

    log_path = config.DATA_DIR / "changes_log.csv"
    with log_path.open("a", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "change", "reason", "rows_affected", "before_summary", "after_summary"],
        )
        writer.writerow(
            {
                "date": date.today().isoformat(),
                "change": "Post-hoc sanity retag of the 105 audit rows into audit_retag_v2.csv",
                "reason": "post-hoc, not an independent test. Agreement was not scored. Human labels and cache.json were not changed.",
                "rows_affected": int(len(out)),
                "before_summary": "Not scored.",
                "after_summary": (
                    "post-hoc, not an independent test. "
                    f"tree {count_values(out['tree_node'], config.TREE_NODES)}. "
                    f"scope {count_values(out['metric_scope'], config.METRIC_SCOPES)}. "
                    f"sip_outcome filled {filled_outcome} of {len(out)}. "
                    f"is_sip_instalment_issue filled {filled_sip} of {len(out)}."
                ),
            }
        )
    return out


def request_tags(client, batch):
    """Ask for tags for this batch. Returns a map of real id to the raw model object."""
    mapping, body = format_batch(batch)
    user = (
        "Tag each comment. Return one result for every id in this batch. "
        "evidence_quote must be copied from that comment.\n" + body
    )
    items = ask_json(client, TAG_SYSTEM, user, RETAG_MAX_TOKENS, RETAG_TEMPERATURE)
    returned = {}
    for item in items:
        if isinstance(item, dict):
            local = str(item.get("id", "")).lower()
            if local in mapping:
                returned[mapping[local]] = item
    return returned


def retag_final_rows(client):
    """Retag every final.csv row at temperature 0. Writes data/final_retag.csv and never writes cache.json."""
    import csv
    from datetime import date

    final = config.read_csv(config.FINAL_CSV)
    if final.empty:
        raise RuntimeError("No final.csv yet.")
    rows = [row for _, row in final.iterrows()]
    batches = (len(rows) + TAG_BATCH - 1) // TAG_BATCH
    seconds = batches * RETAG_SECONDS_PER_BATCH
    print(
        f"Estimate before any API call: {len(rows)} rows, batch size {TAG_BATCH}, "
        f"{batches} API calls if each batch returns all {TAG_BATCH} rows. "
        f"About {seconds // 3600} hours {(seconds % 3600) // 60} minutes "
        f"at {RETAG_SECONDS_PER_BATCH} seconds per batch. Temperature {RETAG_TEMPERATURE}. "
        "A batch that returns fewer rows is sent again immediately, so the call count can be higher. "
        "Output is data/final_retag.csv. data/cache.json will not be written.",
        flush=True,
    )
    stamp = cache_stamp()
    path = config.DATA_DIR / "final_retag.csv"
    done = {}
    if path.exists():
        previous = config.read_csv(path)
        if len(previous) and "id" in previous.columns and len(previous) < len(rows):
            for _, item in previous.iterrows():
                done[item["id"]] = item.to_dict()
            print(f"Resuming. {len(done)} rows are already in {path.name}.", flush=True)
    pending = [row for row in rows if row["id"] not in done]
    print(f"Rows still to tag: {len(pending)}", flush=True)
    rounds = 0
    while pending and rounds < 4:
        still = []
        for start in range(0, len(pending), TAG_BATCH):
            batch = pending[start : start + TAG_BATCH]
            missing = list(batch)
            tries = 0
            while missing and tries < 3:
                tries += 1
                groups = [[row] for row in missing] if tries == 3 and len(missing) > 1 else [missing]
                next_missing = []
                for group in groups:
                    try:
                        returned = request_tags(client, group)
                    except Exception as exc:
                        print(f"  Retag batch failed ({safe_error(exc)}). It will be tried again.", flush=True)
                        next_missing.extend(group)
                        time.sleep(20)
                        continue
                    if len(returned) < len(group):
                        print(f"  partial {len(returned)} of {len(group)}", flush=True)
                    for row in group:
                        raw = returned.get(row["id"])
                        if not raw:
                            next_missing.append(row)
                            continue
                        tag = validate_tag(raw, row["text"], [], row["id"])
                        merged = row.to_dict()
                        merged.update(tag)
                        done[row["id"]] = merged
                    time.sleep(0.6)
                missing = next_missing
            still.extend(missing)
            ordered = [done[row["id"]] for row in rows if row["id"] in done]
            write_rows(pd.DataFrame(ordered), path)
            print(f"  Saved {len(done)} of {len(rows)}", flush=True)
        pending = still
        rounds += 1
        if pending:
            print(f"  {len(pending)} rows still need a tag. Pausing 30s.", flush=True)
            time.sleep(30)
    for row in pending:
        tag = blank_tag()
        merged = row.to_dict()
        merged.update(tag)
        done[row["id"]] = merged
    ordered = [done[row["id"]] for row in rows]
    out = pd.DataFrame(ordered)
    write_rows(out, path)
    now = cache_stamp()
    unchanged = now == stamp
    print("cache.json unchanged" if unchanged else "WARNING cache.json changed", flush=True)
    if not unchanged:
        raise RuntimeError("cache.json changed during the full retag.")
    before_nodes = count_values(final["tree_node"], config.TREE_NODES)
    after_nodes = count_values(out["tree_node"], config.TREE_NODES)
    before_scope = count_values(final["metric_scope"], config.METRIC_SCOPES)
    after_scope = count_values(out["metric_scope"], config.METRIC_SCOPES)
    print("Before tree nodes: " + before_nodes, flush=True)
    print("After tree nodes: " + after_nodes, flush=True)
    print("Before scope: " + before_scope, flush=True)
    print("After scope: " + after_scope, flush=True)
    print("After sip_outcome: " + count_values(out["sip_outcome"], SIP_OUTCOMES), flush=True)
    print(
        "After is_sip_instalment_issue: " + count_values(out["is_sip_instalment_issue"], config.SIP_INSTALMENT_VALUES),
        flush=True,
    )
    missing_tags = int((out["status"].astype(str) == "needs_review").sum()) if "status" in out.columns else 0
    blank_left = len(pending)
    log_path = config.DATA_DIR / "changes_log.csv"
    with log_path.open("a", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "change", "reason", "rows_affected", "before_summary", "after_summary"],
        )
        writer.writerow(
            {
                "date": date.today().isoformat(),
                "change": "Retagged all final rows at temperature 0 into final_retag.csv",
                "reason": "Attempted cancel, stop, pause, or reduce counts as C1 and in_scope. A stated intention with no attempt stays none. A1 and A2 are only setup or the first debit. A later instalment problem is C2, or B1 when it is clearly the 2nd or 3rd instalment. Repeated failure with enough balance is C2. The same prompt now also returns is_sip_instalment_issue and sip_outcome. cache.json was not overwritten.",
                "rows_affected": int(len(out)),
                "before_summary": f"tree {before_nodes}. scope {before_scope}.",
                "after_summary": (
                    f"tree {after_nodes}. scope {after_scope}. "
                    f"sip_outcome {count_values(out['sip_outcome'], SIP_OUTCOMES)}. "
                    f"is_sip_instalment_issue {count_values(out['is_sip_instalment_issue'], config.SIP_INSTALMENT_VALUES)}. "
                    f"needs_review {missing_tags}. unanswered {blank_left}. "
                    f"Temperature {RETAG_TEMPERATURE}. API calls {client.calls}. Saved to final_retag.csv. cache.json unchanged."
                ),
            }
        )
    print(f"Wrote {len(out)} rows to {path.name}. Logged the retag.", flush=True)
    return out


def validate_compact(raw, source_text):
    """Check the short tag. Missing or invalid fields stay blank and the row needs review."""
    tag = {
        "tree_node": "none",
        "metric_scope": "",
        "sip_outcome": "",
        "is_sip_instalment_issue": "",
        "leak_type": "unclear",
        "tenure_hint": "",
        "confusion_point": "",
        "unmet_need": "",
        "workaround": "none",
        "evidence_quote": "",
        "confidence": 0.0,
        "is_relevant": True,
        "status": "needs_review",
    }
    if not isinstance(raw, dict):
        return tag
    valid = True
    tag["tree_node"], ok = one_of(raw.get("tree_node"), config.TREE_NODES, "none")
    valid = valid and ok
    tag["metric_scope"], ok = one_of(raw.get("metric_scope"), config.METRIC_SCOPES, "")
    valid = valid and ok
    tag["sip_outcome"], ok = one_of(raw.get("sip_outcome"), SIP_OUTCOMES, "")
    valid = valid and ok
    tag["is_sip_instalment_issue"], ok = one_of(
        raw.get("is_sip_instalment_issue"), config.SIP_INSTALMENT_VALUES, ""
    )
    valid = valid and ok
    tag["leak_type"], ok = one_of(raw.get("leak_type"), config.LEAK_TYPES, "unclear")
    valid = valid and ok
    tag["tenure_hint"], ok = one_of(raw.get("tenure_hint"), TENURE_HINTS, "")
    valid = valid and ok
    tag["workaround"], ok = one_of(raw.get("workaround"), config.WORKAROUNDS, "none")
    valid = valid and ok
    for field in ("confusion_point", "unmet_need"):
        value = raw.get(field)
        if value is None or str(value).strip().lower() in {"", "null", "none"}:
            tag[field] = ""
            continue
        cleaned, _changed = config.redact_generated(value, source_text)
        tag[field] = "" if cleaned is None else str(cleaned)[:240]
    quote, quote_ok = lock_quote(raw.get("evidence_quote"), source_text)
    tag["evidence_quote"] = quote
    tag["confidence"] = as_confidence(raw.get("confidence"))
    tag["journey_stage"] = TENURE_TO_STAGE.get(tag["tenure_hint"], "unclear")
    tag["workaround_outside_app"] = tag["workaround"]
    if valid and quote_ok and tag["confidence"] >= config.CONFIDENCE_MIN:
        tag["status"] = "ok"
    return tag


def request_compact(client, batch, max_tokens):
    mapping, body = format_batch(batch)
    if len(batch) == 1:
        user = "Tag this one comment. Return one JSON object and no explanation.\n" + body
    else:
        user = (
            "Tag every comment. Return one JSON object per comment, and no explanation.\n" + body
        )
    items = ask_json(client, COMPACT_SYSTEM, user, max_tokens, RETAG_TEMPERATURE)
    returned = {}
    for item in items:
        if isinstance(item, dict):
            local = str(item.get("id", "")).lower()
            if local in mapping:
                returned[mapping[local]] = item
    return returned


def _rows_from(frame):
    return [row for _, row in frame.iterrows()]


def speed_test_compact(client):
    """Time 20 comments two ways. Does not write final_retag.csv or cache.json."""
    import csv
    from datetime import date

    final = config.read_csv(config.FINAL_CSV)
    retag_path = config.DATA_DIR / "final_retag.csv"
    done_ids = set()
    if retag_path.exists():
        previous = config.read_csv(retag_path)
        if len(previous) and "id" in previous.columns:
            done_ids = set(previous["id"])
    groww = final[(final["app"] == "Groww") & ~final["id"].isin(done_ids)]
    rows = _rows_from(groww.head(20))
    if len(rows) < 20:
        raise RuntimeError("Not enough Groww rows left for a 20-row test.")
    stamp = cache_stamp()
    retag_stamp = (retag_path.stat().st_mtime, retag_path.stat().st_size) if retag_path.exists() else None
    print(f"Compact output. max_tokens one comment {COMPACT_MAX_ONE}, five comments {COMPACT_MAX_FIVE}. Temperature {RETAG_TEMPERATURE}.", flush=True)
    print("20-row test. These rows are not written to final_retag.csv.", flush=True)

    def run_mode(mode):
        found = {}
        started = time.time()
        if mode == "batch5":
            for start in range(0, len(rows), 5):
                batch = rows[start : start + 5]
                try:
                    raws = request_compact(client, batch, COMPACT_MAX_FIVE)
                except Exception as exc:
                    print(f"  batch failed ({safe_error(exc)})", flush=True)
                    raws = {}
                for row in batch:
                    raw = raws.get(row["id"])
                    if raw:
                        found[row["id"]] = validate_compact(raw, row["text"])
                print(f"  batch5 saved {len(found)} of {len(rows)}", flush=True)
        else:
            for row in rows:
                try:
                    raws = request_compact(client, [row], COMPACT_MAX_ONE)
                except Exception as exc:
                    print(f"  one failed ({safe_error(exc)})", flush=True)
                    raws = {}
                raw = raws.get(row["id"])
                if raw:
                    found[row["id"]] = validate_compact(raw, row["text"])
            print(f"  one-at-a-time saved {len(found)} of {len(rows)}", flush=True)
        elapsed = time.time() - started
        return found, elapsed

    batch_found, batch_elapsed = run_mode("batch5")
    one_found, one_elapsed = run_mode("one")
    limits_before = client.rate_limits
    parallel_found = {}
    parallel_started = time.time()

    def work(row):
        raws = request_compact(client, [row], COMPACT_MAX_ONE)
        raw = raws.get(row["id"])
        if not raw:
            return row["id"], None
        return row["id"], validate_compact(raw, row["text"])

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as pool:
        futures = [pool.submit(work, row) for row in rows]
        for future in as_completed(futures):
            try:
                row_id, tag = future.result()
            except Exception as exc:
                print(f"  parallel call failed ({safe_error(exc)})", flush=True)
                continue
            if tag:
                parallel_found[row_id] = tag
            print(f"  parallel saved {len(parallel_found)} of {len(rows)}", flush=True)
    parallel_elapsed = time.time() - parallel_started
    new_limits = client.rate_limits - limits_before
    print(
        f"Rate-limit errors during the parallel pass: {new_limits}. "
        f"Workers: {PARALLEL_WORKERS}.",
        flush=True,
    )
    now = cache_stamp()
    retag_now = (retag_path.stat().st_mtime, retag_path.stat().st_size) if retag_path.exists() else None
    print("cache.json unchanged" if now == stamp else "WARNING cache.json changed", flush=True)
    print("final_retag.csv unchanged" if retag_now == retag_stamp else "WARNING final_retag.csv changed", flush=True)

    def line(label, found, elapsed):
        seconds = elapsed / len(rows)
        print(
            f"{label}: {len(found)} of {len(rows)} returned, {elapsed:.1f}s total, {seconds:.2f}s per comment",
            flush=True,
        )
        return seconds

    batch_seconds = line("5 per batch, one call at a time", batch_found, batch_elapsed)
    one_seconds = line("1 comment per call, one call at a time", one_found, one_elapsed)
    parallel_seconds = line(f"1 comment per call, {PARALLEL_WORKERS} at a time", parallel_found, parallel_elapsed)
    batch_full = len(batch_found) == len(rows)
    one_full = len(one_found) == len(rows)
    if batch_full and one_full:
        winner = "5 per batch" if batch_seconds <= one_seconds else "1 comment per call"
    elif batch_full:
        winner = "5 per batch"
    elif one_full:
        winner = "1 comment per call"
    else:
        winner = "5 per batch" if len(batch_found) > len(one_found) else "1 comment per call"
    print(f"Format that is faster and returns the rows: {winner}.", flush=True)
    priority = 73 + 600
    remaining = 2477 - 38
    per = parallel_seconds
    print(
        f"Estimate, not started: {priority} priority rows (Groww left plus 600 competitors) "
        f"at {per:.2f}s per comment in parallel would take about {priority * per / 60:.0f} minutes. "
        f"All {remaining} rows still to tag would take about {remaining * per / 3600:.1f} hours. "
        f"A 2 hour cap would cover about {int(7200 / per) if per else 0} comments.",
        flush=True,
    )
    log_path = config.DATA_DIR / "changes_log.csv"
    with log_path.open("a", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "change", "reason", "rows_affected", "before_summary", "after_summary"],
        )
        writer.writerow(
            {
                "date": date.today().isoformat(),
                "change": "Timed a compact 20-row tag test and did not start the full retag",
                "reason": "The verbose retag was stopped. Output is now a short JSON object. 38 rows already in final_retag.csv were kept. The 2-hour run was not started.",
                "rows_affected": 20,
                "before_summary": "Verbose batches often returned 1 of 5 comments. 38 rows kept.",
                "after_summary": (
                    f"5-per-batch {len(batch_found)} of 20 in {batch_elapsed:.1f}s ({batch_seconds:.2f}s each). "
                    f"1-per-call {len(one_found)} of 20 in {one_elapsed:.1f}s ({one_seconds:.2f}s each). "
                    f"Parallel {PARALLEL_WORKERS} returned {len(parallel_found)} of 20 in {parallel_elapsed:.1f}s "
                    f"({parallel_seconds:.2f}s each). Rate-limit errors in the parallel pass: {new_limits}. "
                    f"Winner: {winner}. Full run not started."
                ),
            }
        )
    return {
        "batch_n": len(batch_found),
        "one_n": len(one_found),
        "parallel_n": len(parallel_found),
        "batch_seconds": batch_seconds,
        "one_seconds": one_seconds,
        "parallel_seconds": parallel_seconds,
        "rate_limits": new_limits,
        "winner": winner,
    }


def _test_rows():
    final = config.read_csv(config.FINAL_CSV)
    done_ids = set()
    retag_path = config.DATA_DIR / "final_retag.csv"
    if retag_path.exists():
        previous = config.read_csv(retag_path)
        if len(previous) and "id" in previous.columns:
            done_ids = set(previous["id"])
    groww = final[(final["app"] == "Groww") & ~final["id"].isin(done_ids)]
    rows = _rows_from(groww.head(20))
    if len(rows) < 20:
        raise RuntimeError("Not enough Groww rows left for a 20-row test.")
    return rows


def _parallel_compact(client, jobs):
    """Run compact tag calls with 5 workers. jobs is a list of row batches."""
    found = {}
    started = time.time()
    limits_before = client.rate_limits

    def work(batch):
        max_tokens = COMPACT_MAX_ONE if len(batch) == 1 else COMPACT_MAX_FIVE
        raws = request_compact(client, batch, max_tokens)
        tagged = {}
        for row in batch:
            raw = raws.get(row["id"])
            if raw:
                tagged[row["id"]] = validate_compact(raw, row["text"])
        return tagged

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as pool:
        futures = [pool.submit(work, batch) for batch in jobs]
        for future in as_completed(futures):
            try:
                found.update(future.result())
            except Exception as exc:
                print(f"  parallel call failed ({safe_error(exc)})", flush=True)
            print(f"  returned {len(found)}", flush=True)
    elapsed = time.time() - started
    return found, elapsed, client.rate_limits - limits_before


def _log_change(change, reason, rows_affected, before_summary, after_summary):
    import csv
    from datetime import date

    log_path = config.DATA_DIR / "changes_log.csv"
    with log_path.open("a", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "change", "reason", "rows_affected", "before_summary", "after_summary"],
        )
        writer.writerow(
            {
                "date": date.today().isoformat(),
                "change": change,
                "reason": reason,
                "rows_affected": rows_affected,
                "before_summary": before_summary,
                "after_summary": after_summary,
            }
        )


def _record_from(row, tag):
    record = {
        key: row.get(key, "")
        for key in (
            "id",
            "source",
            "app",
            "text",
            "rating",
            "date",
            "video_id",
            "context",
            "keyword_count",
        )
    }
    record.update(tag)
    return record


def retag_ordered(client, mode, hours=2, workers=None):
    """Tag any final.csv rows not yet in final_retag.csv. Does not write cache.json."""
    final = config.read_csv(config.FINAL_CSV)
    path = config.DATA_DIR / "final_retag.csv"
    done = {}
    if path.exists():
        previous = config.read_csv(path)
        for _, item in previous.iterrows():
            done[item["id"]] = item.to_dict()
    work = final[~final["id"].isin(set(done))].copy()
    groww = work[work["app"] == "Groww"]
    competitors = work[work["app"].isin(COMPETITOR_APPS)]
    sample_n = min(600, len(competitors))
    sample = competitors.sample(n=sample_n, random_state=7) if sample_n else competitors.iloc[0:0]
    sample_ids = set(sample["id"])
    rest = work[~work["id"].isin(set(groww["id"]) | sample_ids)]
    queue = _rows_from(groww) + _rows_from(sample) + _rows_from(rest)
    if mode == "batch5":
        batches = [queue[start : start + 5] for start in range(0, len(queue), 5)]
    else:
        batches = [[row] for row in queue]
    stamp = cache_stamp()
    worker_count = PARALLEL_WORKERS if workers is None else workers
    deadline = None if not hours else time.time() + hours * 60 * 60
    retry_limit = 8 if deadline is None else 3
    stop_note = "Run until the remaining rows are tagged." if deadline is None else "Stop at 2 hours."
    print(
        f"Starting compact retag. Format {mode}. Workers {worker_count}. "
        f"Queue {len(queue)} ({len(groww)} Groww, {len(sample)} competitor sample, {len(rest)} rest). "
        f"Already saved {len(done)}. {stop_note} cache.json will not be written.",
        flush=True,
    )
    started_with = len(done)
    attempts = {}
    completed = 0
    next_log = 200
    index = 0
    in_flight = {}

    def tag_batch(batch):
        max_tokens = COMPACT_MAX_ONE if len(batch) == 1 else COMPACT_MAX_FIVE
        raws = request_compact(client, batch, max_tokens)
        tagged = {}
        for row in batch:
            raw = raws.get(row["id"])
            if raw:
                tagged[row["id"]] = validate_compact(raw, row["text"])
        return tagged

    def persist():
        records = [done[row_id] for row_id in final["id"] if row_id in done]
        write_rows(pd.DataFrame(records), path)

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        while in_flight or index < len(batches):
            while len(in_flight) < worker_count and index < len(batches) and (deadline is None or time.time() < deadline):
                fut = pool.submit(tag_batch, batches[index])
                in_flight[fut] = batches[index]
                index += 1
            if not in_flight:
                break
            finished, _pending = wait(set(in_flight), return_when=FIRST_COMPLETED)
            for fut in finished:
                batch = in_flight.pop(fut)
                try:
                    tagged = fut.result()
                except Exception as exc:
                    print(f"  batch failed ({safe_error(exc)})", flush=True)
                    tagged = {}
                missing = []
                for row in batch:
                    tag = tagged.get(row["id"])
                    if not tag:
                        missing.append(row)
                        continue
                    done[row["id"]] = _record_from(row, tag)
                    completed += 1
                if missing and (deadline is None or time.time() < deadline):
                    for row in missing:
                        tries = attempts.get(row["id"], 0) + 1
                        attempts[row["id"]] = tries
                        if tries < retry_limit:
                            batches.append([row])
                persist()
                if completed >= next_log:
                    apps = pd.Series([str(done[row_id].get("app", "") or "YouTube, no app") for row_id in done])
                    summary = ", ".join(f"{name} {int(count)}" for name, count in apps.value_counts().items())
                    print(f"Progress {completed} new rows. File now {len(done)}. {summary}", flush=True)
                    _log_change(
                        "Retag progress",
                        f"Compact {mode} retag, {worker_count} workers, temperature 0.",
                        completed,
                        f"Saved before this run: {len(done) - completed}.",
                        f"New rows {completed}. File {len(done)}. {summary}",
                    )
                    next_log += 200
                print(f"  saved {len(done)}", flush=True)
    persist()
    now = cache_stamp()
    if now != stamp:
        raise RuntimeError("cache.json changed during the retag.")
    print("cache.json unchanged", flush=True)
    print(f"Stopped with {len(done)} rows in final_retag.csv. New rows this run: {completed}.", flush=True)
    _log_change(
        "Compact retag stopped",
        "Continued the compact retag for rows not yet saved. cache.json was not overwritten.",
        len(done),
        f"Started from {started_with} previously saved rows. Format {mode}.",
        f"File now {len(done)} rows. New this run {completed}.",
    )
    return done


def compare_parallel_and_maybe_run(client):
    """Time both compact formats at 5 parallel calls. Start the retag only at 5 seconds per comment or faster."""
    rows = _test_rows()
    stamp = cache_stamp()
    retag_path = config.DATA_DIR / "final_retag.csv"
    retag_stamp = (retag_path.stat().st_mtime, retag_path.stat().st_size) if retag_path.exists() else None
    print(
        f"20-row parallel test. Workers {PARALLEL_WORKERS}. Temperature {RETAG_TEMPERATURE}. "
        f"max_tokens one {COMPACT_MAX_ONE}, five {COMPACT_MAX_FIVE}. Not written to final_retag.csv.",
        flush=True,
    )
    batch_jobs = [rows[start : start + 5] for start in range(0, len(rows), 5)]
    one_jobs = [[row] for row in rows]
    print("5 per batch, 5 calls at a time", flush=True)
    batch_found, batch_elapsed, batch_limits = _parallel_compact(client, batch_jobs)
    print("1 comment per call, 5 calls at a time", flush=True)
    one_found, one_elapsed, one_limits = _parallel_compact(client, one_jobs)
    batch_seconds = batch_elapsed / len(rows)
    one_seconds = one_elapsed / len(rows)
    print(
        f"5 per batch: {len(batch_found)} of {len(rows)} returned, {batch_seconds:.2f}s per comment, rate-limit errors {batch_limits}",
        flush=True,
    )
    print(
        f"1 per call: {len(one_found)} of {len(rows)} returned, {one_seconds:.2f}s per comment, rate-limit errors {one_limits}",
        flush=True,
    )
    complete = []
    if len(batch_found) == len(rows):
        complete.append(("batch5", batch_seconds))
    if len(one_found) == len(rows):
        complete.append(("one", one_seconds))
    if not complete:
        choice = "neither format returned every row"
        chosen_seconds = None
        start = False
    else:
        choice, chosen_seconds = min(complete, key=lambda item: item[1])
        start = chosen_seconds <= 5
    if chosen_seconds is None:
        decision = "Did not start. Neither format returned every row."
    elif start:
        decision = f"Chose {choice} at {chosen_seconds:.2f}s per comment and started the run."
    else:
        decision = f"Chose {choice} at {chosen_seconds:.2f}s per comment. Slower than 5s, so the run was not started."
    print(decision, flush=True)
    now = cache_stamp()
    retag_now = (retag_path.stat().st_mtime, retag_path.stat().st_size) if retag_path.exists() else None
    if now != stamp or retag_now != retag_stamp:
        raise RuntimeError("The 20-row test changed cache.json or final_retag.csv.")
    _log_change(
        "Chose the compact retag format",
        "Both formats were timed on 20 comments with 5 parallel calls. The faster format that returned every row is the choice. The run starts only at 5 seconds per comment or less.",
        20,
        f"5 per batch {len(batch_found)} of 20 at {batch_seconds:.2f}s, rate limits {batch_limits}. 1 per call {len(one_found)} of 20 at {one_seconds:.2f}s, rate limits {one_limits}.",
        decision,
    )
    if start:
        retag_ordered(client, choice)
    return chosen_seconds, start


def load_working_set(limit):
    clean = config.read_csv(config.CLEAN_CSV)
    if clean.empty:
        raise RuntimeError("No clean.csv yet. Run 2_clean.py first.")
    if "keyword_count" not in clean.columns:
        clean["keyword_count"] = clean["text"].map(lambda text: config.keyword_count(text, config.KEYWORDS))
    if limit:
        clean = clean.head(limit)
    return clean


def main():
    parser = argparse.ArgumentParser(description="Filter and tag SIP comments")
    parser.add_argument("--limit", type=int, default=0, help="Only the first N clean rows")
    parser.add_argument("--scope-only", action="store_true", help="Add metric_scope to final.csv without retagging")
    parser.add_argument("--instalment-only", action="store_true", help="Add is_sip_instalment_issue without retagging")
    parser.add_argument("--audit-retag", action="store_true", help="Retag only the 105 audit rows and do not write the tag cache")
    parser.add_argument("--audit-sanity", action="store_true", help="Post-hoc retag of the 105 audit rows into audit_retag_v2.csv")
    parser.add_argument("--retag-final", action="store_true", help="Retag final.csv into final_retag.csv without writing cache.json")
    parser.add_argument("--speed-test", action="store_true", help="Time compact tags on 20 rows and do not write them")
    parser.add_argument("--go", action="store_true", help="Time both compact formats, then retag if fast enough")
    parser.add_argument("--finish", action="store_true", help="Tag remaining final.csv rows into final_retag.csv")
    args = parser.parse_args()

    config.ensure_data_dir()
    if args.finish:
        retag_ordered(choose_model(), "one", hours=0, workers=1)
        return
    if args.go:
        compare_parallel_and_maybe_run(choose_model())
        return
    if args.speed_test:
        speed_test_compact(choose_model())
        return
    if args.audit_sanity:
        sanity_audit_retag(choose_model())
        return
    if args.retag_final:
        retag_final_rows(choose_model())
        return
    if args.audit_retag:
        retag_audit_sample(choose_model())
        return
    if args.instalment_only:
        client = choose_model()
        final = config.read_csv(config.FINAL_CSV)
        if final.empty:
            raise RuntimeError("No final.csv yet. Run the tagger first.")
        cache = load_cache()
        instalment_pass(client, final, cache)
        apply_instalment_to_final(cache)
        return
    if args.scope_only:
        client = choose_model()
        final = config.read_csv(config.FINAL_CSV)
        if final.empty:
            raise RuntimeError("No final.csv yet. Run the tagger first.")
        cache = load_cache()
        scope_pass(client, final, cache)
        apply_scope_to_final(cache)
        return
    client = choose_model()
    clean = load_working_set(args.limit)
    cache = load_cache()
    print(f"Working set: {len(clean)}")
    relevant, dropped_ids = relevance_pass(client, clean, cache)

    if not args.limit and len(relevant) < config.FINAL_MIN and config.LOOSE_CSV.exists():
        loose = config.read_csv(config.LOOSE_CSV)
        loose = loose[~loose["id"].isin(set(clean["id"]))]
        if len(loose):
            print(f"Relevant rows are under {config.FINAL_MIN}. Checking {len(loose)} loose-keyword rows.")
            extra, extra_dropped = relevance_pass(client, loose, cache)
            dropped_ids.extend(extra_dropped)
            relevant = pd.concat([relevant, extra], ignore_index=True).drop_duplicates("id")
            print(f"Relevant after loosening the keyword gate: {len(relevant)}")

    if dropped_ids:
        discarded = clean[clean["id"].isin(dropped_ids)]
        if len(discarded):
            sample = discarded.sample(n=min(30, len(discarded)), random_state=19)
            config.write_csv(sample, config.DISCARD_RELEVANCE_CSV)
            print(f"Wrote {len(sample)} discarded relevant-check rows for a spot check")

    config.write_csv(relevant, config.RELEVANT_CSV)
    cache = tag_pass(client, relevant, cache)
    tagged = attach_tags(relevant, cache)
    review_queue = tagged[tagged["status"] == "needs_review"]
    if len(review_queue):
        config.write_csv(review_queue, config.NEEDS_REVIEW_CSV)
    tagged = tagged[tagged["status"] != "dropped"]
    final, ok_count = balance(tagged)
    config.write_csv(final, config.FINAL_CSV)
    config.update_funnel(
        after_relevance=int(len(relevant)),
        after_tag=int(len(tagged)),
        final=int(len(final)),
        final_ok=int(ok_count),
        needs_review=int((final["status"] == "needs_review").sum()) if len(final) else 0,
        model=client.label(),
        api_calls=int(client.calls),
    )
    print(f"OK rows: {ok_count}")
    print(f"Needs review: {int((final['status'] == 'needs_review').sum()) if len(final) else 0}")
    print(f"API calls this run: {client.calls}")
    if ok_count < config.FINAL_MIN:
        print(
            f"Only {ok_count} comments passed with confidence. "
            "The bar was not lowered further."
        )
    print("\n5 sample rows:")
    config.print_samples(final)


if __name__ == "__main__":
    main()
