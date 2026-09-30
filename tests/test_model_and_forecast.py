"""Tests for the LSTM model forward pass, K-step rollout, and MITRE mapper.
These do not require a trained artifact (they build a fresh model)."""
import numpy as np
import torch

from core.schema import load_feature_schema, load_stage_space, mitre_for_stage
from ml.models.lstm_world_model import ModelConfig, build_model


def test_model_forward_shapes():
    schema = load_feature_schema()
    space = load_stage_space()
    cfg = ModelConfig(feature_dim=schema.dim, num_stages=space.num_classes,
                      hidden_size=32, num_layers=1)
    model = build_model(cfg)
    x = torch.rand(4, 10, schema.dim)
    next_state, risk_logit, stage_logits = model(x)
    assert next_state.shape == (4, schema.dim)
    assert risk_logit.shape == (4,)
    assert stage_logits.shape == (4, space.num_classes)


def test_risk_in_unit_interval():
    schema = load_feature_schema()
    space = load_stage_space()
    cfg = ModelConfig(feature_dim=schema.dim, num_stages=space.num_classes,
                      hidden_size=16, num_layers=1)
    model = build_model(cfg)
    r = model.risk(torch.rand(2, 10, schema.dim))
    assert torch.all(r >= 0) and torch.all(r <= 1)


def test_kstep_rollout_length_and_stability():
    """A manual autoregressive rollout should not explode or NaN."""
    schema = load_feature_schema()
    space = load_stage_space()
    cfg = ModelConfig(feature_dim=schema.dim, num_stages=space.num_classes,
                      hidden_size=16, num_layers=1)
    model = build_model(cfg).eval()
    seq = np.random.rand(10, schema.dim).astype(np.float32)
    H = 4
    risks = []
    with torch.no_grad():
        s = seq.copy()
        for _ in range(H + 1):
            x = torch.tensor(s[None, ...], dtype=torch.float32)
            nxt, rl, _ = model(x)
            risks.append(float(torch.sigmoid(rl)[0]))
            s = np.vstack([s[1:], nxt[0].numpy()[None, :]]).astype(np.float32)
    assert len(risks) == H + 1
    assert all(np.isfinite(risks))


def test_mitre_mapper_known_and_unknown():
    m = mitre_for_stage("scanning")
    assert "techniques" in m and any(t["id"] == "T1046" for t in m["techniques"])
    unknown = mitre_for_stage("does_not_exist")
    assert unknown["techniques"] == []


def test_stage_space_indices_contiguous():
    space = load_stage_space()
    ids = [s.id for s in space.stages]
    assert ids == list(range(len(ids)))
    assert space.by_key("normal").id == 0
