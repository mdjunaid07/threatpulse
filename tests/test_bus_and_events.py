"""Tests for event normalization/serialization and the in-memory bus."""
import json

from core.bus import MemoryBus
from core.events import normalize_event, event_to_json, event_from_json


def test_normalize_fills_defaults():
    e = normalize_event({"src_ip": "10.0.0.1"})
    assert e["src_ip"] == "10.0.0.1"
    assert e["dst_port"] == 0
    assert e["ts"] > 0  # defaults to now


def test_event_json_roundtrip():
    e = normalize_event({"src_ip": "10.0.0.1", "dst_port": 443, "history": "S"})
    s = event_to_json(e)
    back = event_from_json(s)
    assert back["dst_port"] == 443
    assert back["history"] == "S"


def test_malformed_json_is_safe():
    e = event_from_json("{not valid json")
    assert e["event_type"] == "invalid"


def test_memory_bus_publish_consume():
    bus = MemoryBus(maxlen=100)
    consumer = bus.consumer()
    # Tail semantics: the first poll subscribes the consumer at the current
    # tail, so events must be published AFTER that first (empty) poll.
    assert consumer.poll("telemetry:zeek") == []
    bus.publish("telemetry:zeek", normalize_event({"src_ip": "10.0.0.9"}))
    bus.publish("telemetry:zeek", normalize_event({"src_ip": "10.0.0.10"}))
    got = consumer.poll("telemetry:zeek", count=10)
    assert len(got) == 2
    assert got[0]["src_ip"] == "10.0.0.9"
    # cursor advanced: no duplicates on next poll
    assert consumer.poll("telemetry:zeek") == []


def test_two_consumers_independent_cursors():
    bus = MemoryBus()
    c1 = bus.consumer()
    c2 = bus.consumer()
    c1.poll("s")  # subscribe both at tail first
    c2.poll("s")
    bus.publish("s", normalize_event({"src_ip": "1.1.1.1"}))
    assert len(c1.poll("s")) == 1
    assert len(c2.poll("s")) == 1
