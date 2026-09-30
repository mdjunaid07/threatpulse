"""features — telemetry -> 10-second network states.

    aggregation      : wall-clock windowing
    network_features : per-window feature math (schema-ordered)
    normalization    : scaler (fit once, load at inference)
    state_builder    : NetworkState + rolling history buffer
"""
