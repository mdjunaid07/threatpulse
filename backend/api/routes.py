"""
backend.api.routes — REST endpoints (querying only; live updates go over
the WebSocket). Every handler reads the shared snapshot the pipeline writes,
so REST and WebSocket always agree.

Optional API-key gate: if settings.api_key is set, requests must send
`X-API-Key`. Left blank in dev so nothing breaks out of the box.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.schema import load_feature_schema, load_stage_space

router = APIRouter(prefix="/api")


def _require_key(x_api_key: str | None = Header(default=None)):
    s = get_settings()
    if s.api_key and x_api_key != s.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
    return True


def _shared(request: Request):
    return request.app.state.shared


def _pipeline(request: Request):
    return request.app.state.pipeline


@router.get("/health")
def health(request: Request):
    shared = _shared(request)
    pipe = _pipeline(request)
    bus = request.app.state.bus
    return {
        "status": "ok",
        "pipeline_running": pipe.running,
        "bus_backend": getattr(bus, "backend", "unknown"),
        "model_status": shared.get_snapshot().get("model_status"),
        "mode": get_settings().mode,
        "ws_clients": request.app.state.ws_manager.client_count,
    }


@router.get("/config")
def config(_: bool = Depends(_require_key)):
    s = get_settings()
    schema = load_feature_schema()
    space = load_stage_space()
    return {
        "app_name": s.app_name,
        "app_full_name": s.app_full_name,
        "team": s.team,
        "mode": s.mode,
        "window_seconds": s.window_seconds,
        "sequence_length": s.sequence_length,
        "forecast_horizon": s.forecast_horizon,
        "feature_count": schema.dim,
        "feature_labels": schema.labels,
        "stages": [{"id": st.id, "key": st.key, "label": st.label, "severity": st.severity}
                   for st in space.stages],
    }


@router.get("/network/status")
def network_status(request: Request, _: bool = Depends(_require_key)):
    snap = _shared(request).get_snapshot()
    return {
        "timestamp": snap["timestamp"],
        "network_status": snap["network_status"],
        "mode": snap.get("mode"),
        "active_hosts": snap.get("active_hosts", 0),
        "active_connections": snap.get("active_connections", 0),
        "events_per_sec": snap.get("events_per_sec", 0.0),
        "current_state": snap.get("current_state", {}),
        "sensor_status": snap.get("sensor_status", {}),
    }


@router.get("/risk")
def risk(request: Request, _: bool = Depends(_require_key)):
    snap = _shared(request).get_snapshot()
    return {
        "risk": snap["risk"],
        "risk_label": snap["risk_label"],
        "model_confidence": snap["model_confidence"],
        "model_status": snap["model_status"],
        "future_risk_timeline": snap["future_risk_timeline"],
        "disclaimer": snap.get("disclaimer"),
    }


@router.get("/forecast")
def forecast(request: Request, _: bool = Depends(_require_key)):
    snap = _shared(request).get_snapshot()
    return {
        "current_stage": snap["current_stage"],
        "forecast_stage": snap["forecast_stage"],
        "stage_distribution": snap.get("stage_distribution", []),
        "future_risk_timeline": snap["future_risk_timeline"],
        "model_confidence": snap["model_confidence"],
        "model_status": snap["model_status"],
        "disclaimer": snap.get("disclaimer"),
    }


@router.get("/attack-stage")
def attack_stage(request: Request, _: bool = Depends(_require_key)):
    snap = _shared(request).get_snapshot()
    return {
        "current_stage": snap["current_stage"],
        "forecast_stage": snap["forecast_stage"],
        "stage_distribution": snap.get("stage_distribution", []),
        "potential_mitre_mappings": snap.get("potential_mitre_mappings", {}),
    }


@router.get("/explanations")
def explanations(request: Request, _: bool = Depends(_require_key)):
    snap = _shared(request).get_snapshot()
    return {
        "top_features": snap.get("top_features", []),
        "model_status": snap["model_status"],
        "note": ("Signed feature attributions from the model. Positive values "
                 "push forecast risk up; they are explanations, not proof of intent."),
    }


@router.get("/events")
def events(request: Request, limit: int = 50, _: bool = Depends(_require_key)):
    shared = _shared(request)
    limit = max(1, min(limit, 200))
    return {"events": shared.recent_events(limit=limit), "total_seen": shared.events_seen}


@router.get("/model")
def model(request: Request, _: bool = Depends(_require_key)):
    pipe = _pipeline(request)
    fc = pipe.forecaster
    return {
        "available": fc.available,
        "model_status": "TRAINED" if fc.available else "NOT_TRAINED",
        "metadata": fc.metadata,
        "train_command": "python -m ml.training.train_lstm",
    }


@router.post("/model/reload")
def model_reload(request: Request, _: bool = Depends(_require_key)):
    ok = _pipeline(request).reload_model()
    return JSONResponse({"reloaded": ok,
                         "available": _pipeline(request).forecaster.available})
