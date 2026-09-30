"""core — shared vocabulary and transport for ThreatPulse.

Modules:
    config          : runtime Settings (config.yaml + env overrides)
    schema          : feature schema, stage labels, MITRE map loaders
    events          : normalized telemetry event shape
    bus             : Redis Streams transport w/ in-memory fallback
    logging_setup   : logging configuration
"""
