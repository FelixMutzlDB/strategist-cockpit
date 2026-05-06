"""Tests for audit.record_event format (SDR F-TM-4)."""

import json
import logging
from unittest.mock import patch

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


# --- F-TM-4 Delta sink (closure of PARTIAL state) -------------------------


def test_record_event_writes_to_delta_when_dbsql_and_token(monkeypatch):
    """When data_backend=dbsql AND user_token is provided, the event is
    mirrored to main.field_strategist_cockpit.app_audit_log via dbsql."""
    from src.backend.config import settings

    monkeypatch.setattr(settings, "data_backend", "dbsql")
    captured = {}

    def fake_execute(token, query, params):
        captured["token"] = token
        captured["query"] = query
        captured["params"] = params

    with patch("src.backend.dbsql.execute", side_effect=fake_execute):
        record_event(
            user_email="alice@databricks.com",
            action="create",
            target_type="engagement",
            target_id=42,
            extra={"prompt_length": 10},
            user_token="OBO-token-xyz",
        )

    assert captured["token"] == "OBO-token-xyz"
    assert "INSERT INTO main.field_strategist_cockpit.app_audit_log" in captured["query"]
    assert captured["params"]["user_email"] == "alice@databricks.com"
    assert captured["params"]["action"] == "create"
    assert captured["params"]["target_type"] == "engagement"
    assert captured["params"]["target_id"] == "42"  # cast to string per DDL
    assert captured["params"]["result"] == "success"
    # extra serialized to JSON string in the dedicated `extra` column.
    assert json.loads(captured["params"]["extra"]) == {"prompt_length": 10}


def test_record_event_skips_delta_when_sqlite(monkeypatch):
    """SQLite-mode dev runs must NOT call into dbsql — the connector
    isn't expected to be reachable."""
    from src.backend.config import settings

    monkeypatch.setattr(settings, "data_backend", "sqlite")
    with patch("src.backend.dbsql.execute") as fake_execute:
        record_event(
            user_email="alice@databricks.com",
            action="create",
            target_type="engagement",
            user_token="OBO",
        )
    fake_execute.assert_not_called()


def test_record_event_skips_delta_when_no_user_token(monkeypatch):
    """Even with dbsql active, no token → no delta write (best-effort)."""
    from src.backend.config import settings

    monkeypatch.setattr(settings, "data_backend", "dbsql")
    with patch("src.backend.dbsql.execute") as fake_execute:
        record_event(
            user_email="alice@databricks.com",
            action="create",
            target_type="engagement",
            user_token=None,
        )
    fake_execute.assert_not_called()


def test_record_event_continues_on_delta_failure(caplog, monkeypatch):
    """Warehouse hiccup must NOT propagate — audit is observability, not
    transactional state. Failure logs a WARNING and the route succeeds."""
    from src.backend.config import settings

    monkeypatch.setattr(settings, "data_backend", "dbsql")
    caplog.set_level(logging.WARNING, logger="strategist_cockpit.audit")

    with patch(
        "src.backend.dbsql.execute",
        side_effect=RuntimeError("warehouse down"),
    ):
        # Must not raise.
        record_event(
            user_email="alice@databricks.com",
            action="create",
            target_type="engagement",
            user_token="OBO",
        )
    assert any(
        "Audit Delta sink failed" in rec.getMessage()
        for rec in caplog.records
        if rec.name == "strategist_cockpit.audit"
    )
