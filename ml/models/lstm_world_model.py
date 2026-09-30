"""
ml.models.lstm_world_model — the temporal World Model.

A lightweight multi-head LSTM (CPU-friendly, ~8 GB RAM target):

    input  (batch, seq_len, feature_dim)   # scaled network states
      -> shared LSTM encoder
      -> last hidden state h
      -> three heads:
           HEAD 1  next_state : Linear(dim)      regression   -> S(t+1) (scaled)
           HEAD 2  risk       : Linear(1)+sigmoid              -> risk in [0,1]
           HEAD 3  stage      : Linear(num_stages)             -> stage logits

The next_state head is what enables K-step autoregressive rollout: predict
S(t+1), append it, predict S(t+2), and so on.

Do NOT swap this for a Transformer/GNN — the spec fixes LSTM for the MVP.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn


@dataclass
class ModelConfig:
    feature_dim: int
    num_stages: int
    hidden_size: int = 96
    num_layers: int = 2
    dropout: float = 0.15

    def to_dict(self) -> dict:
        return {
            "feature_dim": self.feature_dim,
            "num_stages": self.num_stages,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "dropout": self.dropout,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ModelConfig":
        return cls(
            feature_dim=int(d["feature_dim"]),
            num_stages=int(d["num_stages"]),
            hidden_size=int(d.get("hidden_size", 96)),
            num_layers=int(d.get("num_layers", 2)),
            dropout=float(d.get("dropout", 0.15)),
        )


class LSTMWorldModel(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.cfg = cfg
        self.encoder = nn.LSTM(
            input_size=cfg.feature_dim,
            hidden_size=cfg.hidden_size,
            num_layers=cfg.num_layers,
            batch_first=True,
            dropout=cfg.dropout if cfg.num_layers > 1 else 0.0,
        )
        self.head_next = nn.Sequential(
            nn.Linear(cfg.hidden_size, cfg.hidden_size),
            nn.ReLU(),
            nn.Linear(cfg.hidden_size, cfg.feature_dim),
        )
        self.head_risk = nn.Sequential(
            nn.Linear(cfg.hidden_size, cfg.hidden_size // 2),
            nn.ReLU(),
            nn.Linear(cfg.hidden_size // 2, 1),
        )
        self.head_stage = nn.Sequential(
            nn.Linear(cfg.hidden_size, cfg.hidden_size),
            nn.ReLU(),
            nn.Linear(cfg.hidden_size, cfg.num_stages),
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, F) -> last-timestep hidden representation (B, H)
        out, _ = self.encoder(x)
        return out[:, -1, :]

    def forward(self, x: torch.Tensor):
        h = self.encode(x)
        next_state = self.head_next(h)              # (B, F)  scaled next state
        risk_logit = self.head_risk(h).squeeze(-1)  # (B,)
        stage_logits = self.head_stage(h)           # (B, C)
        return next_state, risk_logit, stage_logits

    def risk(self, x: torch.Tensor) -> torch.Tensor:
        _, risk_logit, _ = self.forward(x)
        return torch.sigmoid(risk_logit)


def build_model(cfg: ModelConfig, device: str = "cpu") -> LSTMWorldModel:
    model = LSTMWorldModel(cfg).to(device)
    return model
