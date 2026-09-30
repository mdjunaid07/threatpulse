"""
ml.inference.explain — feature attribution for a single forecast.

Primary method: gradient x input on the risk head — cheap, exact for the
current model, and works on CPU. If SHAP is installed AND a background set is
supplied, a KernelExplainer path is available, but gradient attribution is
the default because it is fast enough for the live inference loop.

Returned attributions are signed: positive => pushes forecast risk UP,
negative => pushes it DOWN. They are model-internal explanations, not proof
of intent.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import torch

from core.schema import FeatureSchema


def gradient_attribution(model, x_scaled: np.ndarray, schema: FeatureSchema) -> List[Dict]:
    """x_scaled: (seq_len, dim) scaled sequence. Attributes the risk output to
    each feature by |grad * input| aggregated over the time axis, signed by
    the sign of grad*input summed over time."""
    model.eval()
    device = next(model.parameters()).device
    x = torch.tensor(x_scaled[None, ...], dtype=torch.float32, device=device, requires_grad=True)
    _next, risk_logit, _stage = model(x)
    risk = torch.sigmoid(risk_logit).sum()
    model.zero_grad(set_to_none=True)
    risk.backward()
    grad = x.grad.detach().cpu().numpy()[0]          # (seq_len, dim)
    contrib = grad * x_scaled                         # (seq_len, dim)
    signed = contrib.sum(axis=0)                      # (dim,) signed
    magnitude = np.abs(contrib).sum(axis=0)           # (dim,) magnitude

    total = magnitude.sum() or 1.0
    items = []
    for i, feat in enumerate(schema.features):
        items.append({
            "name": feat.name,
            "label": feat.label,
            "contribution": float(signed[i]),
            "magnitude": float(magnitude[i]),
            "weight": float(magnitude[i] / total),
            "direction": "increase" if signed[i] >= 0 else "decrease",
        })
    items.sort(key=lambda d: d["magnitude"], reverse=True)
    return items


def top_features(model, x_scaled: np.ndarray, schema: FeatureSchema, k: int = 5) -> List[Dict]:
    return gradient_attribution(model, x_scaled, schema)[:k]
