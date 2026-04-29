"""Tests for audit.record_event format (SDR F-TM-4)."""

import json
import logging

from src.backend.audit import record_event


def test_record_event_emits_structured_json(caplog):
    caplog.set_level(logging.INFO, logger="strategist_cockpit.audit")
    record_event(
        user_email="alice@databricks.com",
        action="create",
        target_type="engagement",
        target_id=42,
    )
    rec = next(r for r in caplog.records if r.name == "strategist_cockpit.audit")
    payload = json.loads(rec.getMessage().split("audit ", 1)[1])
    assert payload["user_email"] == "alice@databricks.com"
    assert payload["action"] == "create"
    assert payload["target_type"] == "engagement"
    assert payload["target_id"] == 42
    assert payload["result"] == "success"
    assert isinstance(payload["ts"], int)


def test_record_event_extra_kept_no_pii(caplog):
    caplog.set_level(logging.INFO, logger="strategist_cockpit.audit")
    record_event(
        user_email="bob@databricks.com",
        action="chat",
        target_type="stratego_ka",
        extra={"prompt_length": 123},
    )
    rec = next(r for r in caplog.records if r.name == "strategist_cockpit.audit")
    payload = json.loads(rec.getMessage().split("audit ", 1)[1])
    assert payload["prompt_length"] == 123
    assert payload["target_id"] is None


def test_record_event_extra_cannot_overwrite_canonical_fields(caplog):
    caplog.set_level(logging.INFO, logger="strategist_cockpit.audit")
    record_event(
        user_email="carol@databricks.com",
        action="delete",
        target_type="project",
        target_id=99,
        extra={"user_email": "OVERRIDE@evil.com", "ts": 0},
    )
    rec = next(r for r in caplog.records if r.name == "strategist_cockpit.audit")
    payload = json.loads(rec.getMessage().split("audit ", 1)[1])
    assert payload["user_email"] == "carol@databricks.com"  # canonical wins
    assert payload["ts"] != 0
