"""
ml.inference.forecaster — load the trained World Model and produce forecasts.

This is what the backend inference loop calls each window. Given the current
raw state sequence [S(t-n)..S(t)] it returns:

  * current risk (0..1) and a coarse label
  * current stage probabilities + argmax stage
  * K-step autoregressive risk timeline (Now, +10s, +20s, ...) using the
    next-state head to roll the world model forward
  * forecast (next) stage
  * signed top feature contributions (explainability)

If artifacts are missing it reports `available=False` and the backend surfaces
"Model: NOT TRAINED" rather than fabricating numbers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from core.config import get_settings
from core.logging_setup import get_logger
from core.schema import load_feature_schema, load_stage_space, mitre_for_stage
from features.normalization import FeatureScaler

log = get_logger("forecaster")


def risk_label(risk: float) -> str:
    if risk < 0.25:
        return "LOW"
    if risk < 0.5:
        return "GUARDED"
    if risk < 0.75:
        return "ELEVATED"
    return "HIGH"


@dataclass
class ForecastResult:
    available: bool
    model_status: str                    # TRAINED | NOT_TRAINED
    dataset_type: str                    # synthetic | dataset_csv | unknown
    risk: float
    risk_label: str
    model_confidence: float              # max stage softmax prob
    current_stage: dict                  # {key,label,severity,prob}
    forecast_stage: dict
    stage_distribution: List[dict]
    future_risk_timeline: List[dict]     # [{offset_seconds, risk, risk_label}]
    top_features: List[dict]
    potential_mitre: dict
    metadata: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "available": self.available,
            "model_status": self.model_status,
            "dataset_type": self.dataset_type,
            "risk": self.risk,
            "risk_label": self.risk_label,
            "model_confidence": self.model_confidence,
            "current_stage": self.current_stage,
            "forecast_stage": self.forecast_stage,
            "stage_distribution": self.stage_distribution,
            "future_risk_timeline": self.future_risk_timeline,
            "top_features": self.top_features,
            "potential_mitre": self.potential_mitre,
            "metadata": self.metadata,
        }


class Forecaster:
    def __init__(self):
        self.settings = get_settings()
        self.schema = load_feature_schema()
        self.space = load_stage_space()
        self.scaler = FeatureScaler(None)
        self.model = None
        self.metadata: dict = {}
        self._torch = None
        self.load()

    # ------------------------------------------------------------------ load
    def load(self) -> bool:
        s = self.settings
        model_path = s.abs_path(s.model_path)
        if not model_path.exists():
            log.warning("Model artifact not found at %s (train first).", model_path)
            self.model = None
            return False
        try:
            import torch
            from ml.models.lstm_world_model import LSTMWorldModel, ModelConfig
            self._torch = torch
            ckpt = torch.load(model_path, map_location=s.device, weights_only=False)
            cfg = ModelConfig.from_dict(ckpt["config"])
            model = LSTMWorldModel(cfg)
            model.load_state_dict(ckpt["state_dict"])
            model.eval()
            self.model = model
            self.scaler = FeatureScaler.load(s.abs_path(s.scaler_path))
            meta_path = s.abs_path(s.metadata_path)
            if meta_path.exists():
                self.metadata = json.loads(meta_path.read_text())
            log.info("Loaded LSTM World Model (dim=%d, stages=%d).",
                     cfg.feature_dim, cfg.num_stages)
            return True
        except Exception as exc:  # pragma: no cover
            log.error("Failed to load model: %s", exc)
            self.model = None
            return False

    @property
    def available(self) -> bool:
        return self.model is not None

    # ------------------------------------------------------------- forecast
    def _unavailable_result(self) -> ForecastResult:
        stages = [{"key": s.key, "label": s.label, "severity": s.severity, "prob": 0.0}
                  for s in self.space.stages]
        normal = {"key": "normal", "label": "Normal", "severity": 0, "prob": 0.0}
        return ForecastResult(
            available=False, model_status="NOT_TRAINED", dataset_type="unknown",
            risk=0.0, risk_label="N/A", model_confidence=0.0,
            current_stage=normal, forecast_stage=normal,
            stage_distribution=stages, future_risk_timeline=[],
            top_features=[], potential_mitre=mitre_for_stage("normal"),
            metadata={"note": "Model not trained. Run: python -m ml.training.train_lstm"},
        )

    def forecast(self, raw_sequence: np.ndarray) -> ForecastResult:
        """raw_sequence: (seq_len, dim) of RAW (unscaled) feature vectors."""
        if not self.available:
            return self._unavailable_result()

        torch = self._torch
        seq = np.asarray(raw_sequence, dtype=np.float32)
        scaled = self.scaler.transform(seq)              # (T, dim) scaled
        x = torch.tensor(scaled[None, ...], dtype=torch.float32)

        with torch.no_grad():
            next_state, risk_logit, stage_logits = self.model(x)
            risk = float(torch.sigmoid(risk_logit)[0].item())
            stage_probs = torch.softmax(stage_logits, dim=1)[0].cpu().numpy()

        # current + forecast stage
        cur_id = int(np.argmax(stage_probs))
        cur_stage = self.space.by_id(cur_id)
        confidence = float(stage_probs[cur_id])
        stage_dist = [
            {"key": s.key, "label": s.label, "severity": s.severity,
             "prob": float(stage_probs[s.id])}
            for s in self.space.stages
        ]

        # K-step autoregressive rollout of risk (and next stage).
        timeline, forecast_stage_id = self._rollout(scaled, risk)

        forecast_stage = self.space.by_id(forecast_stage_id)

        # explainability
        from ml.inference.explain import top_features as _top
        try:
            feats = _top(self.model, scaled, self.schema, k=6)
        except Exception as exc:  # pragma: no cover
            log.warning("attribution failed: %s", exc)
            feats = []

        return ForecastResult(
            available=True,
            model_status="TRAINED",
            dataset_type=self.metadata.get("training_dataset", "unknown"),
            risk=risk,
            risk_label=risk_label(risk),
            model_confidence=confidence,
            current_stage={"key": cur_stage.key, "label": cur_stage.label,
                           "severity": cur_stage.severity, "prob": confidence},
            forecast_stage={"key": forecast_stage.key, "label": forecast_stage.label,
                            "severity": forecast_stage.severity,
                            "prob": float(np.max(self._last_forecast_probs))},
            stage_distribution=stage_dist,
            future_risk_timeline=timeline,
            top_features=feats,
            potential_mitre=mitre_for_stage(cur_stage.key),
            metadata=self.metadata,
        )

    def _rollout(self, scaled_seq: np.ndarray, risk_now: float):
        """Autoregressive K-step forecast. Feed predicted next state back in.
        Returns (timeline, forecast_stage_id)."""
        torch = self._torch
        W = self.settings.window_seconds
        H = self.settings.forecast_horizon
        seq = scaled_seq.copy()                          # (T, dim) scaled

        timeline = [{"offset_seconds": 0, "risk": round(risk_now, 4),
                     "risk_label": risk_label(risk_now)}]
        forecast_stage_id = int(np.argmax(self._stage_probs(seq)))
        self._last_forecast_probs = self._stage_probs(seq)

        for k in range(1, H + 1):
            x = torch.tensor(seq[None, ...], dtype=torch.float32)
            with torch.no_grad():
                next_state, risk_logit, stage_logits = self.model(x)
            r = float(torch.sigmoid(risk_logit)[0].item())
            timeline.append({"offset_seconds": k * W, "risk": round(r, 4),
                             "risk_label": risk_label(r)})
            probs = torch.softmax(stage_logits, dim=1)[0].cpu().numpy()
            if k == H:
                forecast_stage_id = int(np.argmax(probs))
                self._last_forecast_probs = probs
            # roll the window: drop oldest, append predicted next state
            nxt = next_state[0].cpu().numpy()
            seq = np.vstack([seq[1:], nxt[None, :]]).astype(np.float32)

        return timeline, forecast_stage_id

    def _stage_probs(self, scaled_seq: np.ndarray) -> np.ndarray:
        torch = self._torch
        x = torch.tensor(scaled_seq[None, ...], dtype=torch.float32)
        with torch.no_grad():
            _n, _r, stage_logits = self.model(x)
        return torch.softmax(stage_logits, dim=1)[0].cpu().numpy()


_FORECASTER: Optional[Forecaster] = None


def get_forecaster() -> Forecaster:
    global _FORECASTER
    if _FORECASTER is None:
        _FORECASTER = Forecaster()
    return _FORECASTER
