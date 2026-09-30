"""
features.normalization — feature scaler used for BOTH training and inference.

Wraps sklearn StandardScaler. The scaler is FIT ONCE on training data and
saved to disk (models/scaler.pkl); at inference it is only LOADED and used
to transform. Never fit on live data (that would leak and drift).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

try:
    import joblib
except Exception:  # pragma: no cover
    joblib = None

from sklearn.preprocessing import StandardScaler


class FeatureScaler:
    def __init__(self, scaler: Optional[StandardScaler] = None):
        self._scaler = scaler

    @property
    def fitted(self) -> bool:
        return self._scaler is not None and hasattr(self._scaler, "mean_")

    def fit(self, X: np.ndarray) -> "FeatureScaler":
        X = np.asarray(X, dtype=np.float64)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        self._scaler = StandardScaler()
        self._scaler.fit(X)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform a (n, dim) or (dim,) array. If not fitted, returns input
        unchanged (identity) so the pipeline still runs before training."""
        X = np.asarray(X, dtype=np.float64)
        single = X.ndim == 1
        if single:
            X = X[None, :]
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        if self.fitted:
            X = self._scaler.transform(X)
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        out = X.astype(np.float32)
        return out[0] if single else out

    def save(self, path: str | Path) -> None:
        if joblib is None:
            raise RuntimeError("joblib is required to save the scaler")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._scaler, path)

    @classmethod
    def load(cls, path: str | Path) -> "FeatureScaler":
        path = Path(path)
        if joblib is None or not path.exists():
            return cls(None)
        try:
            return cls(joblib.load(path))
        except Exception:
            return cls(None)
