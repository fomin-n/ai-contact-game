"""Tests for log rotation in backend/app/event_log.py.

These swap out the module's production RotatingFileHandler for a temporary
one pointed at a tmp dir with tiny maxBytes/backupCount, so rotation can be
exercised without writing 20MB of data. The original handler is restored in
tearDown so other tests' write_event() calls keep working normally.
"""
from __future__ import annotations

import json
import logging.handlers
import os
import tempfile
import unittest
from pathlib import Path

from backend.app import event_log


class EventLogRotationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.log_file = Path(self.tmpdir.name) / "test.jsonl"
        self._original_handlers = list(event_log._event_logger.handlers)
        for handler in self._original_handlers:
            event_log._event_logger.removeHandler(handler)
        self._handler = logging.handlers.RotatingFileHandler(
            self.log_file, maxBytes=500, backupCount=3, encoding="utf-8"
        )
        self._handler.setFormatter(logging.Formatter("%(message)s"))
        event_log._event_logger.addHandler(self._handler)

    def tearDown(self) -> None:
        event_log._event_logger.removeHandler(self._handler)
        self._handler.close()
        for handler in self._original_handlers:
            event_log._event_logger.addHandler(handler)
        self.tmpdir.cleanup()

    def _backups(self) -> list[Path]:
        return sorted(self.log_file.parent.glob(f"{self.log_file.name}.*"))

    def test_rotation_creates_backup_file_when_size_exceeded(self) -> None:
        for i in range(50):
            event_log.write_event("test_event", index=i, payload="x" * 50)

        self.assertTrue(self.log_file.exists())
        self.assertTrue((self.log_file.with_name(self.log_file.name + ".1")).exists())

    def test_active_file_stays_near_max_bytes_after_rotation(self) -> None:
        for i in range(200):
            event_log.write_event("test_event", index=i, payload="x" * 50)

        # The active file can exceed maxBytes by up to one record (rotation is
        # checked before each write, not mid-write), but should never grow
        # unboundedly.
        self.assertLess(self.log_file.stat().st_size, 500 * 3)

    def test_backup_count_is_respected(self) -> None:
        for i in range(500):
            event_log.write_event("test_event", index=i, payload="x" * 50)

        self.assertLessEqual(len(self._backups()), 3)

    def test_jsonl_format_is_unchanged(self) -> None:
        event_log.write_event("test_event", foo="bar")

        lines = self.log_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["eventType"], "test_event")
        self.assertEqual(record["foo"], "bar")
        self.assertIn("ts", record)
        self.assertIn("time", record)

    def test_redaction_still_applied_after_rotation_swap(self) -> None:
        os.environ["MISTRAL_API_KEY"] = "supersecretkeyvalue123"
        try:
            event_log.write_event("test_event", note="key=supersecretkeyvalue123")
        finally:
            del os.environ["MISTRAL_API_KEY"]

        content = self.log_file.read_text(encoding="utf-8")
        self.assertNotIn("supersecretkeyvalue123", content)
        self.assertIn("[REDACTED]", content)

    def test_sensitive_key_names_still_redacted(self) -> None:
        event_log.write_event("test_event", apiKey="literal-secret-value")

        content = self.log_file.read_text(encoding="utf-8")
        self.assertNotIn("literal-secret-value", content)
        self.assertIn("[REDACTED]", content)


if __name__ == "__main__":
    unittest.main()
