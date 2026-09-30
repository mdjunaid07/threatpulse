"""Tests for the feature engine, aggregation, normalization and state buffer.
Run without Kali/Zeek/Suricata."""
import numpy as np

from core.events import normalize_event, is_failed_conn
from core.schema import load_feature_schema
from features.network_features import build_feature_vector, compute_raw_features
from features.aggregation import WindowAccumulator
from features.normalization import FeatureScaler
from features.state_builder import NetworkState, StateHistoryBuffer


def _conn(**kw):
    base = {"event_type": "conn", "src_ip": "10.0.0.5", "dst_ip": "10.0.0.10",
            "dst_port": 80, "proto": "tcp", "history": "ShADadfF",
            "conn_state": "SF", "orig_pkts": 5, "resp_pkts": 5,
            "orig_bytes": 500, "resp_bytes": 500, "ts": 1.0}
    base.update(kw)
    return normalize_event(base)


def test_schema_dim_matches_vector():
    schema = load_feature_schema()
    vec, named = build_feature_vector([_conn()], schema, ["10.0.0.0/8"])
    assert vec.shape == (schema.dim,)
    assert set(schema.names).issubset(named.keys())


def test_empty_window_is_zero_and_finite():
    schema = load_feature_schema()
    vec, _ = build_feature_vector([], schema, [])
    assert vec.shape == (schema.dim,)
    assert np.all(np.isfinite(vec))
    assert vec.sum() == 0.0


def test_scanning_increases_port_diversity_and_failures():
    schema = load_feature_schema()
    normal = [_conn(dst_port=80) for _ in range(10)]
    scan = [_conn(dst_port=p, conn_state="S0", history="S", resp_pkts=0)
            for p in range(1, 200)]
    _, n_named = build_feature_vector(normal, schema, ["10.0.0.0/8"])
    _, s_named = build_feature_vector(scan, schema, ["10.0.0.0/8"])
    assert s_named["unique_dst_ports"] > n_named["unique_dst_ports"]
    assert s_named["connection_failure_rate"] > n_named["connection_failure_rate"]


def test_failed_conn_detection():
    assert is_failed_conn(normalize_event({"conn_state": "S0"}))
    assert not is_failed_conn(normalize_event({"conn_state": "SF"}))


def test_clipping_applied():
    schema = load_feature_schema()
    many = [_conn() for _ in range(10000)]
    _, named = build_feature_vector(many, schema, [])
    # total_connections has clip_max 5000 in the schema
    assert named["total_connections"] <= 5000


def test_window_accumulator_closes():
    acc = WindowAccumulator(window_seconds=10)
    acc.add_many([_conn(), _conn()])
    assert acc.pending_count() == 2
    assert acc.due(now=acc._window_start + 11)
    start, end, events = acc.close(now=acc._window_start + 11)
    assert len(events) == 2
    assert acc.pending_count() == 0


def test_scaler_identity_when_unfit():
    sc = FeatureScaler(None)
    x = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    out = sc.transform(x)
    assert np.allclose(out, x)


def test_scaler_fit_transform_roundtrip(tmp_path):
    sc = FeatureScaler().fit(np.random.rand(50, 4))
    x = np.random.rand(4)
    out = sc.transform(x)
    assert out.shape == (4,)
    p = tmp_path / "scaler.pkl"
    sc.save(p)
    loaded = FeatureScaler.load(p)
    assert loaded.fitted


def test_history_buffer_pads_to_sequence_length():
    schema = load_feature_schema()
    buf = StateHistoryBuffer(sequence_length=10, dim=schema.dim)
    st = NetworkState(ts=1, window_start=0, window_end=1,
                      vector=np.ones(schema.dim, np.float32), named={},
                      event_count=1)
    buf.append(st)
    mat = buf.sequence_matrix()
    assert mat.shape == (10, schema.dim)  # padded
    assert not buf.full
