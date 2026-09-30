"""
core.schema — loaders for the feature schema, stage labels and MITRE map.

These three YAML files are the shared vocabulary of the whole system.
Everything (feature engine, model I/O dimensions, training targets, API,
frontend) derives its notion of "how many features" and "which stages"
from here, so nothing is hard-coded in two places.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import yaml

from core.config import REPO_ROOT

CONFIG_DIR = REPO_ROOT / "configs"


@dataclass(frozen=True)
class Feature:
    name: str
    label: str
    direction: str
    clip_max: float | None


@dataclass(frozen=True)
class FeatureSchema:
    version: int
    window_seconds: int
    features: List[Feature]

    @property
    def names(self) -> List[str]:
        return [f.name for f in self.features]

    @property
    def labels(self) -> List[str]:
        return [f.label for f in self.features]

    @property
    def dim(self) -> int:
        """State-vector length, derived from the schema (never hard-coded)."""
        return len(self.features)

    def index(self, name: str) -> int:
        return self.names.index(name)


@dataclass(frozen=True)
class Stage:
    id: int
    key: str
    label: str
    severity: int


@dataclass(frozen=True)
class StageSpace:
    version: int
    stages: List[Stage]

    @property
    def num_classes(self) -> int:
        return len(self.stages)

    @property
    def keys(self) -> List[str]:
        return [s.key for s in self.stages]

    @property
    def labels(self) -> List[str]:
        return [s.label for s in self.stages]

    def by_id(self, idx: int) -> Stage:
        return self.stages[idx]

    def by_key(self, key: str) -> Stage:
        for s in self.stages:
            if s.key == key:
                return s
        raise KeyError(key)


@lru_cache(maxsize=1)
def load_feature_schema() -> FeatureSchema:
    with open(CONFIG_DIR / "feature_schema.yaml", "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    feats = [
        Feature(
            name=f["name"],
            label=f.get("label", f["name"]),
            direction=f.get("direction", "neutral"),
            clip_max=f.get("clip_max"),
        )
        for f in raw["features"]
    ]
    return FeatureSchema(
        version=raw.get("version", 1),
        window_seconds=raw.get("window_seconds", 10),
        features=feats,
    )


@lru_cache(maxsize=1)
def load_stage_space() -> StageSpace:
    with open(CONFIG_DIR / "stage_labels.yaml", "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    stages = [
        Stage(id=s["id"], key=s["key"], label=s["label"], severity=s.get("severity", 0))
        for s in sorted(raw["stages"], key=lambda x: x["id"])
    ]
    return StageSpace(version=raw.get("version", 1), stages=stages)


@lru_cache(maxsize=1)
def load_mitre_map() -> Dict[str, dict]:
    with open(CONFIG_DIR / "mitre_map.yaml", "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return raw.get("mappings", {})


def mitre_for_stage(stage_key: str) -> dict:
    """Return the potential-ATT&CK mapping block for a stage key.
    Always returns a dict (empty-ish for unknown keys)."""
    mp = load_mitre_map()
    return mp.get(
        stage_key,
        {"tactic": "N/A", "techniques": [], "note": "No mapping available."},
    )
