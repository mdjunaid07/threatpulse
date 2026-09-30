"""
sensor.collectors.base — a robust file tailer.

Zeek and Suricata both write newline-delimited log files that we tail. This
base class follows a file like `tail -F`: it handles the file not existing
yet, being truncated, or being rotated (inode change), and never raises out
of its polling loop. Subclasses implement `parse_line` to turn one raw line
into zero or more normalized events.

Design decision: tailing plain log files (rather than a Zeek/Suricata plugin)
keeps the collector decoupled and lets it run as an ordinary unprivileged
process on Ubuntu, reading logs the sensors already produce.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Iterable, List, Optional

from core.logging_setup import get_logger


class TailCollector:
    name = "base"

    def __init__(self, path: str, bus, stream: str, poll_interval: float = 0.5):
        self.path = str(path)
        self.bus = bus
        self.stream = stream
        self.poll_interval = poll_interval
        self.log = get_logger(f"collector.{self.name}")
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._published = 0
        self._last_error: Optional[str] = None
        self._present = False

    # ---- to be overridden ----
    def parse_line(self, line: str) -> List[dict]:
        raise NotImplementedError

    # ---- lifecycle ----
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"{self.name}-tail", daemon=True)
        self._thread.start()
        self.log.info("%s collector tailing %s -> %s", self.name, self.path, self.stream)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    @property
    def status(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "present": self._present,
            "published": self._published,
            "last_error": self._last_error,
            "running": bool(self._thread and self._thread.is_alive()),
        }

    # ---- core tail loop ----
    def _run(self) -> None:
        fh = None
        inode = None
        while not self._stop.is_set():
            try:
                if not os.path.exists(self.path):
                    self._present = False
                    if fh:
                        fh.close()
                        fh = None
                    self._stop.wait(self.poll_interval * 2)
                    continue

                st = os.stat(self.path)
                if fh is None or inode != st.st_ino:
                    # (Re)open on first sight or rotation.
                    if fh:
                        fh.close()
                    fh = open(self.path, "r", encoding="utf-8", errors="replace")
                    # Start at end so we only stream *new* telemetry.
                    fh.seek(0, os.SEEK_END)
                    inode = st.st_ino
                    self._present = True
                    self._last_error = None

                # Handle truncation (file got smaller).
                if fh.tell() > st.st_size:
                    fh.seek(0, os.SEEK_END)

                line = fh.readline()
                if not line:
                    self._stop.wait(self.poll_interval)
                    continue

                line = line.strip()
                if not line:
                    continue
                for event in self.parse_line(line):
                    if event:
                        self.bus.publish(self.stream, event)
                        self._published += 1
            except Exception as exc:  # never die
                self._last_error = str(exc)
                self.log.debug("%s tail error: %s", self.name, exc)
                self._stop.wait(self.poll_interval)
        if fh:
            fh.close()
