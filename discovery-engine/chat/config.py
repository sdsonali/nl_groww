"""Thresholds for the SIP help chat.

Do not lower CONFIDENCE_MIN to make an eval score look better.
Log any change in eval/changes_log.csv.
"""

import importlib.util
from pathlib import Path

CONFIDENCE_MIN = 0.6
MAX_ANSWER_WORDS = 120
DISCLAIMER = "AI assistant. General information, not investment advice."
SUPPORT_URL = "TODO-VERIFY"

_ROOT = None


def discovery_root():
    return Path(__file__).resolve().parents[1]


def discovery_config():
    """The engine config that already holds the NVIDIA model name and key."""
    global _ROOT
    if _ROOT is not None:
        return _ROOT
    path = discovery_root() / "config.py"
    spec = importlib.util.spec_from_file_location("discovery_config", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _ROOT = module
    return module
