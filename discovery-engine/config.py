"""Settings for the SIP discovery engine.

Keywords, store ids, the metric tree, and fixability scores live here.
Fixability is a PM judgement. Change the scores and reasons by hand.
The model is not allowed to set them.
"""

import json
import os
import re
from pathlib import Path

import pandas as pd
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_CSV = DATA_DIR / "raw.csv"
CLEAN_CSV = DATA_DIR / "clean.csv"
LOOSE_CSV = DATA_DIR / "loose.csv"
RELEVANT_CSV = DATA_DIR / "relevant.csv"
FINAL_CSV = DATA_DIR / "final.csv"
RANKING_CSV = DATA_DIR / "ranking.csv"
GOLDEN_CSV = DATA_DIR / "golden.csv"
CORRECTIONS_CSV = DATA_DIR / "corrections.csv"
CACHE_JSON = DATA_DIR / "cache.json"
FUNNEL_JSON = DATA_DIR / "funnel.json"
MODEL_JSON = DATA_DIR / "model_used.json"
VIDEOS_CSV = DATA_DIR / "videos.csv"
SEBI_LOG = DATA_DIR / "sebi_log.csv"
DISCARD_KEYWORD_CSV = DATA_DIR / "discarded_keyword_sample.csv"
DISCARD_RELEVANCE_CSV = DATA_DIR / "discarded_relevance_sample.csv"
NEEDS_REVIEW_CSV = DATA_DIR / "needs_review.csv"

RAW_COLUMNS = [
    "id",
    "source",
    "app",
    "text",
    "rating",
    "date",
    "video_id",
    "context",
]

FORBIDDEN_COLUMNS = {
    "username",
    "user_name",
    "userName",
    "author",
    "author_name",
    "profile",
    "profile_url",
    "profile_link",
    "channel_id",
    "channel_title",
    "user_id",
    "email",
}

# Free-credit instruct models on the Hugging Face router.
# Prices are USD per 1M tokens. None of the router models are flagged free,
# so these are the ones a free account can finish inside the monthly credit.
CANDIDATE_MODELS = [
    {
        "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "provider": "nscale",
        "size": 7,
        "input_price": 0.01,
        "output_price": 0.03,
    },
    {
        "model": "meta-llama/Llama-3.1-8B-Instruct",
        "provider": "deepinfra",
        "size": 8,
        "input_price": 0.02,
        "output_price": 0.05,
    },
    {
        "model": "Qwen/Qwen3-4B-Instruct-2507",
        "provider": "nscale",
        "size": 4,
        "input_price": 0.01,
        "output_price": 0.03,
    },
]

# Groq's free-tier model, used only when HF cannot complete the task and a key exists.
GROQ_MODEL = "llama-3.1-8b-instant"

# Free-tier Gemini model. 3.8 Flash is stronger but was returning 503 on this account.
GEMINI_MODEL = "gemini-3.5-flash"

# NVIDIA's free prototyping endpoint. The older nemotron-3-super id now returns 410.
NVIDIA_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"

PLAY_APPS = [
    {
        "app": "Groww",
        "package": "com.nextbillion.groww",
        "apple_id": "1404871703",
        "max_reviews": 20000,
    },
    {
        "app": "Zerodha Coin",
        "package": "com.zerodha.coin",
        "apple_id": "1392892554",
        "max_reviews": 5000,
    },
    {
        "app": "INDmoney",
        "package": "in.indwealth",
        "apple_id": "1450178837",
        "max_reviews": 5000,
    },
    {
        "app": "ET Money",
        "package": "com.smartspends",
        "apple_id": "1212752482",
        "max_reviews": 5000,
    },
    {
        "app": "Kuvera",
        "package": "com.gooogle.android.kuvera.app",
        "apple_id": "1329701793",
        "max_reviews": 5000,
    },
    {
        "app": "Paytm Money",
        "package": "com.paytmmoney",
        "apple_id": "1344431352",
        "max_reviews": 5000,
    },
]

YOUTUBE_QUERIES = [
    "SIP for beginners India",
    "should I continue my SIP",
    "I stopped my SIP mutual fund",
    "SIP instalment failed India",
    "SIP band kar du",
    "mutual fund SIP pause or cancel",
    "SIP mandate bounce",
    "first time mutual fund SIP experience India",
    "groww SIP failed",
    "groww SIP cancel",
    "SIP autopay failed India",
    "SIP mandate expired mutual fund",
    "SIP bounce insufficient balance",
    "mutual fund SIP stopped India",
]

# Optional extra videos. Leave empty to use search only.
YOUTUBE_VIDEO_IDS = []

KEYWORDS = [
    "sip",
    "mutual fund",
    "mutual funds",
    "instalment",
    "installment",
    "autopay",
    "auto pay",
    "auto debit",
    "auto-debit",
    "autodebit",
    "mandate",
    "nach",
    "e-nach",
    "enach",
    "nav",
    "folio",
    "paused",
    "stopped",
    "cancel",
    "cancelled",
    "canceled",
    "skipped",
    "bounce",
    "bounced",
    "failed",
    "statement",
    "xirr",
    "step up",
    "step-up",
    "stepup",
    "redeem",
    "redeemed",
    "withdraw",
    "withdrawal",
    "sip band",
    "band kar",
    "paisa kat",
    "nahi kata",
    "nahi kaata",
    "sip rok",
    "sip chalu",
    "sip start",
    "systematic investment",
    "monthly sip",
    "sip amount",
    "sip date",
    "ecs",
]

# Used only if the strict gate leaves fewer than 1,500 relevant comments.
LOOSE_KEYWORDS = KEYWORDS + [
    "deducted",
    "deduction",
    "units allotted",
    "allotment",
    "monthly investment",
    "sip ka",
    "upi autopay",
    "auto-pay",
]

KEYWORD_CAP = 6000
FINAL_CAP = 3000
FINAL_MIN = 1500
GROWW_SHARE_MIN = 0.40
SOURCE_SHARE_MAX = 0.60
CONFIDENCE_MIN = 0.6

# metric_scope: is this comment about continuing a SIP?
# in_scope: the comment is about starting, continuing, pausing, reducing, failing, restarting, or understanding a SIP instalment while the person is still investing or deciding whether to continue.
# exit_experience: the person has already decided to leave and the comment is about the exit itself (redemption speed, withdrawal delay, account closure, post-exit support).
# other_platform_complaint: complaints about fees, paid plans, reports, KYC, UI bugs, or other features that do not mention a SIP instalment, a pause, or a stop.
# unclear: cannot tell. Goes to the needs-review list.
METRIC_SCOPES = ("in_scope", "exit_experience", "other_platform_complaint", "unclear")

# is_sip_instalment_issue: Does this comment clearly say a recurring SIP instalment, autopay, or mandate failed, was missed, or was not debited? A one-time payment, add-money failure, or login/KYC error is no.
SIP_INSTALMENT_VALUES = ("yes", "no", "unclear")
SIP_INSTALMENT_NODES = ("C1", "C2", "C3", "A1", "B1")

TREE = {
    "A1": "SIP set up and first instalment debited successfully",
    "A2": "Setup completed without abandoning",
    "B1": "2nd and 3rd instalments succeed",
    "B2": "Investor does not cancel after first statement or first look at value",
    "C1": "Voluntary leaks: pause, cancel, reduce, redeem and leave",
    "C2": "Involuntary leaks: failed debit, expired mandate, bank change, low balance",
    "C3": "Failed-debit recovery: user notices and fixes it in time",
    "D1": "Instalment successful in the last 30 days",
    "E1": "Paused or failed users who restart",
    "none": "No tree node",
}

STAGES = {
    "A1": "start",
    "A2": "start",
    "B1": "settle_in_m1_3",
    "B2": "settle_in_m1_3",
    "C1": "middle_m4_9",
    "C2": "middle_m4_9",
    "C3": "middle_m4_9",
    "D1": "month_12_plus",
    "E1": "restart",
    "none": "unclear",
}

# PM judgement. Edit the score and the reason yourself. Do not let a model set these.
FIXABILITY = {
    "A1": {
        "score": 3,
        "reason": "A first debit that does not go through is usually a mandate, bank, or balance step the app can explain and let the user retry.",
    },
    "A2": {
        "score": 3,
        "reason": "People who leave during setup need a shorter flow that saves progress and shows which step is left.",
    },
    "B1": {
        "score": 2,
        "reason": "The app can warn before the second and third debit, but the balance itself sits with the bank.",
    },
    "B2": {
        "score": 2,
        "reason": "The app can show instalment status next to the current value so a lower value is not read as a failed SIP.",
    },
    "C1": {
        "score": 2,
        "reason": "Pause, reduce, and cancel are the user's choice. The app can explain what each option does, without pushing them to stay.",
    },
    "C2": {
        "score": 3,
        "reason": "Failed debits, an expired mandate, and a bank change are flows the app can detect and explain in plain language.",
    },
    "C3": {
        "score": 3,
        "reason": "A plain alert that a debit failed, with a path to update the mandate, is an in-app fix.",
    },
    "D1": {
        "score": 1,
        "reason": "Month 12 is the result of earlier steps. There is little to change at that point alone.",
    },
    "E1": {
        "score": 2,
        "reason": "A restart path can be easy to find. The decision to restart stays with the user.",
    },
    "none": {
        "score": 1,
        "reason": "No leak to fix in the app.",
    },
}

SEVERITY = {
    "cancelled": 3,
    "failed_debit": 3,
    "paused": 2,
    "reduced": 2,
    "considering": 1,
    "continued": 1,
    "restarted": 1,
    "none": 1,
}

JOURNEY_STAGES = [
    "start",
    "settle_in_m1_3",
    "middle_m4_9",
    "month_12_plus",
    "restart",
    "unclear",
]
TREE_NODES = list(TREE.keys())
LEAK_TYPES = ["voluntary", "involuntary", "none", "unclear"]
ACTIONS = [
    "paused",
    "cancelled",
    "reduced",
    "continued",
    "failed_debit",
    "restarted",
    "considering",
    "none",
]
CHECKS = [
    "app_value",
    "nav",
    "statement",
    "returns_calculator",
    "news",
    "none",
    "unclear",
]
WORKAROUNDS = [
    "google",
    "youtube",
    "friends_family",
    "advisor",
    "calculator",
    "other",
    "none",
]
INCOME_TYPES = ["salaried", "irregular", "student", "unclear"]
AGE_HINTS = ["under_25", "25_35", "35_plus", "unclear"]
INFLUENCES = ["friend", "youtuber", "app_nudge", "family", "self", "unclear"]
EMOTIONS = [
    "confused",
    "anxious",
    "disappointed",
    "neutral",
    "satisfied",
    "angry",
]

TAG_FIELDS = [
    "is_relevant",
    "journey_stage",
    "tree_node",
    "leak_type",
    "action_taken",
    "trigger",
    "confusion_point",
    "what_they_check",
    "workaround_outside_app",
    "income_type",
    "age_hint",
    "influenced_by",
    "emotion",
    "unmet_need",
    "evidence_quote",
    "confidence",
]

NOT_ADVICE = "Analysis of public comments. Not investment advice."
VOCAL_NOTE = (
    "Comments show what vocal users say, not true population rates. "
    "Quiet drop-offs are covered in interviews."
)
SMALL_SAMPLE_NOTE = "Fewer than 30 comments. This is a hint, not a rate."

# Names the model must not introduce. The phrase "mutual fund" is allowed.
BLOCK_TERMS = [
    "parag parikh",
    "sbi bluechip",
    "sbi small cap",
    "hdfc flexi",
    "hdfc mid-cap",
    "hdfc mid cap",
    "icici prudential",
    "nippon india",
    "mirae asset",
    "axis bluechip",
    "axis small cap",
    "quant small cap",
    "quant flexi",
    "motilal oswal",
    "kotak flexi",
    "uti nifty",
    "nifty bees",
    "bank bees",
    "reliance industries",
    "tata consultancy",
    "infosys",
    "hdfc bank",
    "icici bank",
]

FEAR_PHRASES = [
    "hurry",
    "act now",
    "last chance",
    "don't miss",
    "do not miss",
    "you will regret",
    "you'll regret",
    "limited time",
    "before it's too late",
    "fomo",
]


def load_env():
    """Load keys from discovery-engine/.env only. That file replaces older values."""
    path = ROOT / ".env"
    if not path.exists():
        return
    values = {}
    for key, value in dotenv_values(path).items():
        if value and str(value).strip():
            values[key] = str(value).strip()
    chosen = (values.get("HF_TOKEN") or values.get("HUGGINGFACE_API_KEY") or "").strip()
    if chosen:
        values["HF_TOKEN"] = chosen
        values["HUGGINGFACE_API_KEY"] = chosen
    for key, value in values.items():
        os.environ[key] = value


load_env()


def env_value(*names):
    for name in names:
        value = os.environ.get(name, "")
        if value and value.strip():
            return value.strip()
    return ""


HF_TOKEN = env_value("HF_TOKEN", "HUGGINGFACE_API_KEY")
HF_MODEL = env_value("HF_MODEL")
HF_PROVIDER = env_value("HF_PROVIDER")
YOUTUBE_API_KEY = env_value("YOUTUBE_API_KEY")
GROQ_API_KEY = env_value("GROQ_API_KEY")
NVIDIA_API_KEY = env_value("NVIDIA_API_KEY")
GEMINI_API_KEY = env_value("GEMINI_API_KEY")
GEMINI_KEYS = []
for _gemini_name in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"):
    _gemini_value = env_value(_gemini_name)
    if _gemini_value and _gemini_value not in GEMINI_KEYS:
        GEMINI_KEYS.append(_gemini_value)


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_csv(path):
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def assert_no_identifiers(df):
    bad = [col for col in df.columns if col in FORBIDDEN_COLUMNS or "username" in col.lower()]
    if bad:
        raise RuntimeError("Refusing to save identifier columns: " + ", ".join(bad))


def write_csv(df, path):
    ensure_data_dir()
    assert_no_identifiers(df)
    df.to_csv(path, index=False)


def update_funnel(**kwargs):
    ensure_data_dir()
    current = {}
    if FUNNEL_JSON.exists():
        try:
            current = json.loads(FUNNEL_JSON.read_text())
        except json.JSONDecodeError:
            current = {}
    current.update(kwargs)
    FUNNEL_JSON.write_text(json.dumps(current, indent=2))


def load_funnel():
    if not FUNNEL_JSON.exists():
        return {}
    try:
        return json.loads(FUNNEL_JSON.read_text())
    except json.JSONDecodeError:
        return {}


def print_samples(df, n=5):
    if df is None or df.empty:
        print("No rows to show.")
        return
    view = df.sample(n=min(n, len(df)), random_state=7)
    for _, row in view.iterrows():
        text = re.sub(r"\s+", " ", str(row.get("text", "")))[:160]
        print(f"- [{row.get('source', '')} | {row.get('app', '')}] {text}")


def keyword_count(text, keywords):
    """Count keyword hits. Short words must be whole words so 'nav' skips 'navigation'."""
    lowered = str(text).lower()
    count = 0
    for word in keywords:
        if any(mark in word for mark in (" ", "-", "'")):
            if word in lowered:
                count += 1
        elif re.search(r"\b" + re.escape(word) + r"\b", lowered):
            count += 1
    return count


def redact_generated(field, source_text):
    """Replace a model-written field that names a fund or stock, or uses fear."""
    if field is None:
        return field, False
    text = str(field).strip()
    if not text or text.lower() in {"none", "null", "unclear"}:
        return text, False
    lowered = text.lower()
    source = str(source_text).lower()
    for term in BLOCK_TERMS:
        if term in lowered and term not in source:
            return "Not available", True
    for phrase in FEAR_PHRASES:
        if phrase in lowered:
            return "Not available", True
    return text, False
