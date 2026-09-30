"""
core.config — central configuration loader.

Loads configs/config.yaml, then applies environment-variable overrides
(from the process environment, which python-dotenv can populate from a
local .env file). Exposes a single cached `get_settings()` accessor.

Design decision: one typed Settings object built once and shared, so the
feature engine, model, backend and collectors all agree on window size,
sequence length, stream names, etc. No module hard-codes these.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List

import yaml

try:  # optional: load a .env file if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass


# Repository root = parent of the `core` package directory.
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "configs" / "config.yaml"


def _env(name: str, default):
    """Return env override for `name` if present, else `default`.
    Empty-string env values are treated as 'unset' so blank .env lines
    fall back to config defaults."""
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    return val


def _as_int(v, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _as_bool(v, default: bool) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class RedisSettings:
    host: str
    port: int
    db: int
    password: str
    streams: dict
    consumer_group: str
    maxlen: int


@dataclass
class Settings:
    # app
    app_name: str
    app_full_name: str
    team: str
    host: str
    port: int
    env: str
    # mode
    mode: str
    # windowing
    window_seconds: int
    sequence_length: int
    forecast_horizon: int
    # redis
    redis: RedisSettings
    # model
    model_path: str
    scaler_path: str
    metadata_path: str
    device: str
    hidden_size: int
    num_layers: int
    dropout: float
    # lab
    kali_ip: str
    ubuntu_ip: str
    monitor_interface: str
    victim_interface: str
    internal_cidrs: List[str]
    # sensors
    zeek_enabled: bool
    zeek_log_dir: str
    zeek_conn_log: str
    suricata_enabled: bool
    suricata_eve_path: str
    # frontend / security
    frontend_origin: str
    cors_origins: List[str]
    api_key: str
    # paths
    repo_root: Path = field(default=REPO_ROOT)

    def abs_path(self, p: str) -> Path:
        """Resolve a possibly-relative path against the repo root."""
        path = Path(p)
        return path if path.is_absolute() else (self.repo_root / path)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}

    app = cfg.get("app", {})
    win = cfg.get("windowing", {})
    rds = cfg.get("redis", {})
    mdl = cfg.get("model", {})
    lab = cfg.get("lab", {})
    sensors = cfg.get("sensors", {})
    zeek = sensors.get("zeek", {})
    suri = sensors.get("suricata", {})
    fe = cfg.get("frontend", {})
    sec = cfg.get("security", {})

    redis = RedisSettings(
        host=_env("REDIS_HOST", rds.get("host", "127.0.0.1")),
        port=_as_int(_env("REDIS_PORT", rds.get("port", 6379)), 6379),
        db=_as_int(_env("REDIS_DB", rds.get("db", 0)), 0),
        password=_env("REDIS_PASSWORD", rds.get("password", "")),
        streams=rds.get("streams", {}),
        consumer_group=rds.get("consumer_group", "forecaster"),
        maxlen=_as_int(rds.get("maxlen", 20000), 20000),
    )

    cors = sec.get("cors_origins", []) or []
    frontend_origin = _env("FRONTEND_ORIGIN", fe.get("origin", "http://localhost:5173"))
    if frontend_origin not in cors:
        cors = [frontend_origin, *cors]

    return Settings(
        app_name=app.get("name", "ThreatPulse"),
        app_full_name=app.get("full_name", "AI-Based Network Attack Forecasting"),
        team=app.get("team", "NeuroVex"),
        host=_env("APP_HOST", app.get("host", "0.0.0.0")),
        port=_as_int(_env("APP_PORT", app.get("port", 8000)), 8000),
        env=_env("APP_ENV", app.get("env", "development")),
        mode=str(_env("SYSTEM_MODE", cfg.get("mode", "replay"))).lower(),
        window_seconds=_as_int(_env("WINDOW_SECONDS", win.get("window_seconds", 10)), 10),
        sequence_length=_as_int(_env("SEQUENCE_LENGTH", win.get("sequence_length", 10)), 10),
        forecast_horizon=_as_int(_env("FORECAST_HORIZON", win.get("forecast_horizon", 4)), 4),
        redis=redis,
        model_path=_env("MODEL_PATH", mdl.get("path", "models/lstm_world_model.pt")),
        scaler_path=_env("SCALER_PATH", mdl.get("scaler_path", "models/scaler.pkl")),
        metadata_path=mdl.get("metadata_path", "models/training_metadata.json"),
        device=_env("MODEL_DEVICE", mdl.get("device", "cpu")),
        hidden_size=_as_int(mdl.get("hidden_size", 96), 96),
        num_layers=_as_int(mdl.get("num_layers", 2), 2),
        dropout=float(mdl.get("dropout", 0.15)),
        kali_ip=_env("KALI_IP", lab.get("kali_ip", "")),
        ubuntu_ip=_env("UBUNTU_IP", lab.get("ubuntu_ip", "")),
        monitor_interface=_env("MONITOR_INTERFACE", lab.get("monitor_interface", "")),
        victim_interface=_env("VICTIM_INTERFACE", lab.get("victim_interface", "")),
        internal_cidrs=lab.get("internal_cidrs", []),
        zeek_enabled=_as_bool(_env("ZEEK_ENABLED", zeek.get("enabled", True)), True),
        zeek_log_dir=_env("ZEEK_LOG_DIR", zeek.get("log_dir", "/opt/zeek/logs/current")),
        zeek_conn_log=zeek.get("conn_log", "conn.log"),
        suricata_enabled=_as_bool(_env("SURICATA_ENABLED", suri.get("enabled", True)), True),
        suricata_eve_path=_env("SURICATA_EVE_PATH", suri.get("eve_path", "/var/log/suricata/eve.json")),
        frontend_origin=frontend_origin,
        cors_origins=cors,
        api_key=_env("API_KEY", sec.get("api_key", "")),
    )
