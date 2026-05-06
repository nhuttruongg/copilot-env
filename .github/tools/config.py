"""Config loader for the Copilot agentic environment.

Loads .github/config.yaml, resolves "auto" values, exposes a Config dataclass.
Profile resolution itself happens in Task 4 (resolve_profile); this module
only loads + validates the raw config.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml


@dataclass
class Config:
    profile: str
    profile_thresholds: dict[str, dict[str, int]]
    features: dict[str, str]
    codegraph: dict[str, Any]
    memory_budgets: dict[str, dict[str, int]]
    memory_compaction_model: str
    memory_archive_after_days: int
    dispatch: dict[str, Any]
    models: dict[str, Any]
    routing: dict[str, Any]
    raw: dict[str, Any] = field(repr=False)


VALID_PROFILES = {"auto", "tiny", "small", "medium", "large", "xlarge", "custom"}


def load_config(path: Path) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    raw = yaml.safe_load(path.read_text()) or {}
    profile = raw.get("profile", "auto")
    if profile not in VALID_PROFILES:
        raise ValueError(f"invalid profile {profile!r}; must be one of {sorted(VALID_PROFILES)}")
    return Config(
        profile=profile,
        profile_thresholds=raw.get("profile_thresholds", {}),
        features=raw.get("features", {}),
        codegraph=raw.get("codegraph", {}),
        memory_budgets=raw.get("memory", {}).get("budgets", {}),
        memory_compaction_model=raw.get("memory", {}).get("compaction_model", "claude-sonnet-4-6"),
        memory_archive_after_days=int(raw.get("memory", {}).get("archive_after_days", 7)),
        dispatch=raw.get("dispatch", {}),
        models=raw.get("models", {}),
        routing=raw.get("routing", {}),
        raw=raw,
    )


PROFILE_DEFAULTS: dict[str, dict[str, str]] = {
    "tiny": {
        "code_graph": "off",
        "memory_compaction": "off",
        "multi_agent": "off",
        "worktree_isolation": "off",
        "validator_gate": "optional",
    },
    "small": {
        "code_graph": "symbols-only",
        "memory_compaction": "on",
        "multi_agent": "off",
        "worktree_isolation": "off",
        "validator_gate": "optional",
    },
    "medium": {
        "code_graph": "full",
        "memory_compaction": "on",
        "multi_agent": "on",
        "worktree_isolation": "off",
        "validator_gate": "mandatory",
    },
    "large": {
        "code_graph": "full",
        "memory_compaction": "on",
        "multi_agent": "on",
        "worktree_isolation": "on",
        "validator_gate": "mandatory",
    },
    "xlarge": {
        "code_graph": "full",
        "memory_compaction": "on",
        "multi_agent": "on",
        "worktree_isolation": "on",
        "validator_gate": "mandatory",
    },
}


def resolve_profile(files: int, loc: int, thresholds: dict[str, dict[str, int]]) -> str:
    """Pick the profile whose thresholds the project fits within.

    Both files AND loc must be within the tier's max for it to apply; whichever
    tier has any dimension exceeded escalates to the next tier.
    """
    order = ["tiny", "small", "medium", "large"]
    for tier in order:
        t = thresholds.get(tier, {})
        if files <= t.get("max_files", 0) and loc <= t.get("max_loc", 0):
            return tier
    return "xlarge"


def resolve_feature(feature: str, value: str, profile: str) -> str:
    """If value is 'auto', look up the profile default for the feature.

    Profile 'custom' with auto raises (custom requires explicit values).
    """
    if value != "auto":
        return value
    if profile == "custom":
        raise ValueError(f"profile=custom requires explicit value for feature {feature!r}")
    if profile == "auto":
        profile = "medium"
    defaults = PROFILE_DEFAULTS.get(profile, {})
    if feature not in defaults:
        raise KeyError(f"unknown feature {feature!r} for profile {profile!r}")
    return defaults[feature]
