import functools
from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yml"


@functools.lru_cache(maxsize=1)
def _load_config() -> dict:
    """Read and parse config.yml once per process — result is cached."""
    with open(_CONFIG_PATH, "r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file) or {}


def load_instructions(agent_name: str) -> str:
    """Return the instructions string for *agent_name* from config.yml.

    Falls back to the 'default' key when the agent name is not found.
    Returns an empty string when neither key exists.
    """
    config = _load_config()
    agents_config = config if isinstance(config, dict) else {}
    entry = agents_config.get(agent_name) or agents_config.get("default") or {}
    return entry.get("instructions", "")
