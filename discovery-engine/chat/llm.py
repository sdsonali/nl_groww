"""One NVIDIA call, using the same client the discovery engine already uses."""

import importlib.util

from chat.config import discovery_config, discovery_root


def _model_client_class():
    path = discovery_root() / "3_filter_tag.py"
    spec = importlib.util.spec_from_file_location("discovery_tagger", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ModelClient


def complete(system, user, max_tokens):
    """Temperature 0. NVIDIA only. Raises if the key is missing or the call fails."""
    root = discovery_config()
    if not root.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA API key is not set")
    client_cls = _model_client_class()
    client = client_cls(
        {"backend": "nvidia", "model": root.NVIDIA_MODEL, "provider": "nvidia"}
    )
    return client.complete(system, user, max_tokens, temperature=0)
