"""T-217: one-shot migration from the Strategist Tracking Sheet → UC activity tables.

Reads four tabs (Evangelism, Initiatives, Focused Acct Planning, Exec Meetings)
from Google Sheet 1GkqX-xt1pWXsfSwoNFPPcGfgcOfMdccV_6iEZe5IK3U, parses each
row into the shape of the corresponding UC table, stages the result as Parquet
in a UC volume, and (when --apply is set) MERGEs into
main.field_strategist_cockpit.<table> on the natural keys defined in T-217.

The script is deliberately a single file with module-private helpers. The
parser functions (date, quarter, status markers, CXO bool) are pure and
covered by tests/test_migration_parsers.py.

Usage:
    # Default safe mode — read sheet, parse, stage Parquet, write report.
    python scripts/migrate_strategist_activity_from_sheet.py --tab all

    # Same, single tab:
    python scripts/migrate_strategist_activity_from_sheet.py --tab evangelism

    # Promote staged Parquet into UC via MERGE INTO (writes!):
    python scripts/migrate_strategist_activity_from_sheet.py --tab all --apply

    # Override rejects path:
    python scripts/migrate_strategist_activity_from_sheet.py \\
        --tab evangelism --rejects-path /tmp/evangelism_rejects.parquet

Environment:
    DATABRICKS_HOST                   workspace host (required for --apply)
    DATABRICKS_TOKEN                  PAT (required for --apply)
    DATABRICKS_WAREHOUSE_ID           default 071969b1ec9a91ca (logfood)
    STRATEGIST_EMAIL                  default felix.mutzl@databricks.com
    GOOGLE_AUTH_SCRIPT                path to google_auth.py token helper
    GOOGLE_USER_PROJECT               default gcp-dev-field-eng-aiapiquota

Default mode is --dry-run; --apply must be passed explicitly. The script
never writes to the sheet — Felix archives manually after spot-checking.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger("migrate_strategist_activity_from_sheet")

# -------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------- #

SHEET_ID = "1GkqX-xt1pWXsfSwoNFPPcGfgcOfMdccV_6iEZe5IK3U"
DEFAULT_WAREHOUSE_ID = "071969b1ec9a91ca"
DEFAULT_STAGING_VOLUME = "/Volumes/main/field_strategist_cockpit/staging"
DEFAULT_STRATEGIST_EMAIL = "felix.mutzl@databricks.com"
DEFAULT_GOOGLE_AUTH = (
    "/Users/felix.mutzl/.vibe/marketplace/plugins/fe-google-tools/"
    "skills/google-auth/resources/google_auth.py"
)
DEFAULT_GOOGLE_USER_PROJECT = "gcp-dev-field-eng-aiapiquota"

TAB_RANGES = {
    "evangelism": ("Evangelism", "A1:L1000"),
    "initiatives": ("Initiatives", "A1:E1000"),
    "focused_account_planning": ("Focused Acct Planning", "A1:I1000"),
    "exec_meetings": ("Exec Meetings", "A1:G1000"),
}

TARGET_TABLE = {
    "evangelism": "main.field_strategist_cockpit.evangelism_events",
    "initiatives": "main.field_strategist_cockpit.initiatives",
    "focused_account_planning": "main.field_strategist_cockpit.focused_account_planning",
    "exec_meetings": "main.field_strategist_cockpit.exec_meetings",
}

# Natural-key columns per table (see T-217 spec).
NATURAL_KEYS = {
    "evangelism": ("strategist_email", "event_name", "event_date"),
    "initiatives": ("strategist_email", "name"),
    "focused_account_planning": ("strategist_email", "customer", "session_date"),
    "exec_meetings": ("strategist_email", "customer", "exec_name", "meeting_date"),
}

# Allowed enums (light validation — the DDL doesn't enforce CHECK
# constraints, so we reject on unknown values rather than let garbage land).
EVENT_TYPES = {
    "Keynote", "Breakout", "Workshop", "Podcast",
    "Moderation", "Roundtable", "Lightning Talk", "Other",
}
PLANNING_TYPES = {"Focused", "Light"}

# -------------------------------------------------------------------------- #
# Parsers (pure, module-private — covered by tests/test_migration_parsers.py)
# -------------------------------------------------------------------------- #

# Month-name → number map. Supports both short ("Sept" / "Sep") and full names.
_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def parse_date(raw: Any) -> date | None:
    """Parse a free-form date string into a `date`.

    Tries (in order): DD.MM.YYYY → M/D/YYYY → 'D Month YYYY' → 'D Mon YYYY' →
    ISO YYYY-MM-DD. Returns None on no match.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    # DD.MM.YYYY (German). Reject obvious M/D/YYYY style by checking month range.
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d)
        except ValueError:
            return None

    # M/D/YYYY (US).
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d)
        except ValueError:
            return None

    # ISO YYYY-MM-DD.
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d)
        except ValueError:
            return None

    # "D Month YYYY" or "D Mon YYYY" (English).
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{4})", s)
    if m:
        d = int(m.group(1))
        month_name = m.group(2).lower().rstrip(".")
        y = int(m.group(3))
        mo = _MONTHS.get(month_name)
        if mo is not None:
            try:
                return date(y, mo, d)
            except ValueError:
                return None

    return None


def derive_fy_from_date(d: date | None) -> str | None:
    """Databricks fiscal year starts in February.

    FY26 = Feb 2025 – Jan 2026. So a Feb 2025 date is FY26, a Jan 2026 date is
    FY26, a Feb 2026 date is FY27.
    """
    if d is None:
        return None
    fy_num = d.year + 1 if d.month >= 2 else d.year
    return f"FY{fy_num % 100:02d}"


def derive_quarter_from_date(d: date | None) -> str | None:
    """Compute fiscal quarter (Q1=Feb-Apr, Q2=May-Jul, Q3=Aug-Oct, Q4=Nov-Jan)."""
    if d is None:
        return None
    fy = derive_fy_from_date(d)
    if fy is None:
        return None
    # Month 2 → Q1, ..., Month 1 → Q4
    if d.month >= 2:
        q = (d.month - 2) // 3 + 1
    else:
        q = 4
    return f"{fy}Q{q}"


def normalize_quarter(raw: Any, d: date | None = None, fy_hint: str | None = None) -> str | None:
    """Normalize raw quarter strings to canonical `FYxxQn`.

    Accepts: 'FY26Q1', 'FY26-Q1', 'Q2' (combined with fy_hint or derived from
    `d`). Missing → derive from `d` alone.
    """
    s = ("" if raw is None else str(raw)).strip()
    if not s:
        return derive_quarter_from_date(d)

    # FY26Q1 (canonical).
    m = re.fullmatch(r"FY(\d{2})Q(\d)", s, re.IGNORECASE)
    if m:
        return f"FY{m.group(1)}Q{m.group(2)}"

    # FY26-Q1 → FY26Q1.
    m = re.fullmatch(r"FY(\d{2})-Q(\d)", s, re.IGNORECASE)
    if m:
        return f"FY{m.group(1)}Q{m.group(2)}"

    # Bare Q2 — combine with fy_hint, else derive from date.
    m = re.fullmatch(r"Q(\d)", s, re.IGNORECASE)
    if m:
        q = m.group(1)
        fy = (fy_hint or derive_fy_from_date(d) or "").upper()
        if re.fullmatch(r"FY\d{2}", fy):
            return f"{fy}Q{q}"
        return None

    return None


_EVANGELISM_COMPLETE = re.compile(r"\[complete\]", re.IGNORECASE)


def parse_evangelism_status(next_steps: Any, event_date: date | None, today: date | None = None) -> str:
    """Evangelism status: scan Next Steps for [complete]; else past→delivered, future→planned.

    Literal-token match (the bracketed `[complete]`). Free prose like "complete
    the slides" is NOT a match — see test_status_marker_evangelism.
    """
    s = "" if next_steps is None else str(next_steps)
    if _EVANGELISM_COMPLETE.search(s):
        return "delivered"
    if event_date is None:
        # No date → can't decide planned vs delivered; assume delivered so we
        # don't surface unknown-future events as "planned".
        return "delivered"
    today = today or date.today()
    return "planned" if event_date >= today else "delivered"


_INITIATIVE_MARKERS = {
    "on_hold": re.compile(r"---\s*on\s*hold\s*---", re.IGNORECASE),
    "paused": re.compile(r"---\s*paused\s*---", re.IGNORECASE),
    "complete": re.compile(r"---\s*complete\s*---", re.IGNORECASE),
}


def parse_initiative_status(next_steps: Any) -> str:
    """Initiative status from `--- on hold ---` / `--- paused ---` / `--- complete ---` markers.

    First match wins (checked in dict order: on_hold → paused → complete).
    Default is `active`.
    """
    s = "" if next_steps is None else str(next_steps)
    for status, pattern in _INITIATIVE_MARKERS.items():
        if pattern.search(s):
            return status
    return "active"


_TRUE_TOKENS = {"true", "1", "yes", "y"}
_FALSE_TOKENS = {"false", "0", "no", "n", ""}


def parse_cxo_bool(raw: Any) -> bool:
    """CXO column: TRUE/true/1 → True; FALSE/false/0/empty → False.

    Unknown tokens default to False (conservative — better to under-count CXOs
    than to inflate).
    """
    if raw is None:
        return False
    s = str(raw).strip().lower()
    if s in _TRUE_TOKENS:
        return True
    return False


def parse_int(raw: Any) -> int | None:
    """Parse free-form int. Strips commas / whitespace. Returns None on failure."""
    if raw is None:
        return None
    s = str(raw).strip().replace(",", "")
    if not s:
        return None
    try:
        # Allow "800.0" style (Sheets exports decimals sometimes).
        return int(float(s))
    except ValueError:
        return None


_INITIATIVE_NAME_LINK_SUFFIX = re.compile(r"\s*\[link\]\s*$", re.IGNORECASE)


def clean_initiative_name(raw: Any) -> str:
    """Strip the trailing ` [link]` marker the sheet uses to flag click-throughs."""
    s = "" if raw is None else str(raw).strip()
    return _INITIATIVE_NAME_LINK_SUFFIX.sub("", s).strip()


# -------------------------------------------------------------------------- #
# Sheet reader
# -------------------------------------------------------------------------- #


def _get_google_token(auth_script: str) -> str:
    out = subprocess.check_output(["python3", auth_script, "token"]).decode().strip()
    if not out:
        raise RuntimeError("google_auth.py returned an empty token")
    return out


def read_sheet_tab(tab_title: str, sheet_range: str, *, auth_script: str, user_project: str) -> list[list[str]]:
    """Read a single tab range. Returns a list of rows (first row = headers)."""
    token = _get_google_token(auth_script)
    encoded_range = urllib.parse.quote(f"{tab_title}!{sheet_range}", safe="!:")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{encoded_range}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "x-goog-user-project": user_project,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    return payload.get("values", [])


# -------------------------------------------------------------------------- #
# Per-tab row parsers
# -------------------------------------------------------------------------- #


@dataclass
class ParsedRow:
    """A single normalized row ready for parquet staging."""

    fields: dict[str, Any]


@dataclass
class RejectRow:
    """A row that failed parsing — preserved with the original payload + reason."""

    original_row_json: str
    reason: str


@dataclass
class TabStats:
    """Counters surfaced in the diff report."""

    tab: str
    rows_read: int = 0
    rows_parsed: int = 0
    rows_rejected: int = 0
    comments_text_dropped: int = 0  # evangelism only
    notes: list[str] = field(default_factory=list)


def _row_to_dict(row: list[str], headers: list[str]) -> dict[str, str]:
    """Pad row to len(headers) so missing trailing cells become ''."""
    padded = list(row) + [""] * (len(headers) - len(row))
    return {h.strip(): v for h, v in zip(headers, padded, strict=False)}


def parse_evangelism_row(
    row: list[str],
    headers: list[str],
    strategist_email: str,
    *,
    today: date | None = None,
) -> tuple[ParsedRow | None, RejectRow | None, dict[str, int]]:
    """Parse one Evangelism row.

    Headers seen in the sheet (with trailing-space quirks):
        Event | Type | Title | Date | Location | FY | Quarter | Resources
        | # of participants  | # of views | Comments | Next Steps
    """
    stats_inc: dict[str, int] = {}
    raw = _row_to_dict(row, headers)
    event_name = (raw.get("Event") or "").strip()
    if not event_name:
        # Skip blank trailing rows silently — not a reject.
        return None, None, stats_inc

    event_date = parse_date(raw.get("Date"))
    if event_date is None and (raw.get("Date") or "").strip():
        return None, RejectRow(
            original_row_json=json.dumps(raw),
            reason=f"evangelism: unparseable date {raw.get('Date')!r}",
        ), stats_inc

    event_type = (raw.get("Type") or "").strip() or None
    if event_type and event_type not in EVENT_TYPES:
        # Unknown event_type — keep the row but log under notes (the DDL
        # doesn't constrain it; downstream dashboards will warn).
        stats_inc["unknown_event_type"] = stats_inc.get("unknown_event_type", 0) + 1

    fy_raw = (raw.get("FY") or "").strip() or None
    fy = fy_raw or derive_fy_from_date(event_date)
    quarter = normalize_quarter(raw.get("Quarter"), event_date, fy)

    next_steps = (raw.get("Next Steps") or "").strip() or None
    status = parse_evangelism_status(next_steps, event_date, today=today)

    # Evangelism's "Comments" column is BIGINT in the target schema (intended
    # for podcast comment counts). The sheet has free-text prose in most
    # rows. Parse as int when possible; on text fallback, log under
    # comments_text_dropped and store NULL.
    comments_raw = (raw.get("Comments") or "").strip()
    comments_int: int | None = None
    if comments_raw:
        comments_int = parse_int(comments_raw)
        if comments_int is None:
            stats_inc["comments_text_dropped"] = stats_inc.get("comments_text_dropped", 0) + 1

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    parsed = ParsedRow(
        fields=dict(
            strategist_email=strategist_email,
            event_name=event_name,
            event_type=event_type,
            title=(raw.get("Title") or "").strip() or None,
            event_date=event_date,
            location=(raw.get("Location") or "").strip() or None,
            fy=fy,
            quarter=quarter,
            resources=(raw.get("Resources") or "").strip() or None,
            # The sheet header has a trailing space — _row_to_dict strips it.
            participants=parse_int(raw.get("# of participants")),
            views=parse_int(raw.get("# of views")),
            comments=comments_int,
            status=status,
            next_steps=next_steps,
            created_at=now,
            updated_at=now,
        )
    )
    return parsed, None, stats_inc


def parse_initiative_row(
    row: list[str],
    headers: list[str],
    strategist_email: str,
    *,
    today: date | None = None,
) -> tuple[ParsedRow | None, RejectRow | None, dict[str, int]]:
    """Parse one Initiative row.

    Headers: Initiative | FEIP | Actionable Outcome | Resources | Next steps
    """
    stats_inc: dict[str, int] = {}
    raw = _row_to_dict(row, headers)
    name = clean_initiative_name(raw.get("Initiative"))
    if not name:
        return None, None, stats_inc

    next_steps = (raw.get("Next steps") or "").strip() or None
    status = parse_initiative_status(next_steps)

    # Best-effort `last_activity_at` from the most recent `[Mon DD]` bullet in
    # Next steps. Falls back to None (which will surface as NULL).
    last_activity = _extract_latest_dated_bullet(next_steps, today=today)

    # FY: initiatives have no explicit FY column. Derive from last_activity
    # when available, else leave NULL.
    fy = derive_fy_from_date(last_activity) if last_activity else None

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    parsed = ParsedRow(
        fields=dict(
            strategist_email=strategist_email,
            name=name,
            feip_ticket=(raw.get("FEIP") or "").strip() or None,
            actionable_outcome=(raw.get("Actionable Outcome") or "").strip() or None,
            resources=(raw.get("Resources") or "").strip() or None,
            status=status,
            fy=fy,
            next_steps=next_steps,
            last_activity_at=last_activity,
            created_at=now,
            updated_at=now,
        )
    )
    return parsed, None, stats_inc


# Match both orderings the sheet uses:
#   [Oct 15], [Sep 25]               (month-first, no year)
#   [15 Aug], [13 May]               (day-first, no year)
#   [15 Jun 2024], [6 June 2024]    (day-first with year)
#   [Jun 15 2024]                    (month-first with year)
_DATED_BULLET_MONTH_FIRST = re.compile(
    r"\[(?P<month>[A-Za-z]+)\.?\s+(?P<day>\d{1,2})(?:\s+(?P<year>\d{4}))?\]",
)
_DATED_BULLET_DAY_FIRST = re.compile(
    r"\[(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+)\.?(?:\s+(?P<year>\d{4}))?\]",
)


def _extract_latest_dated_bullet(text: str | None, *, today: date | None = None) -> date | None:
    """Find the most recent `[Mon DD]` (or `[DD Mon YYYY]`) bullet in `text`.

    The Initiatives sheet uses prose like:
        [Oct 15] prepared invitation text
        [15 Aug] POC Hackathon

    Year is usually elided. We infer it: if the implied date is in the future
    relative to `today`, roll back a year.
    """
    if not text:
        return None
    today = today or date.today()
    candidates: list[date] = []
    for pattern in (_DATED_BULLET_MONTH_FIRST, _DATED_BULLET_DAY_FIRST):
        for m in pattern.finditer(text):
            try:
                day = int(m.group("day"))
            except (TypeError, ValueError):
                continue
            month_name = m.group("month").lower().rstrip(".")
            year_raw = m.group("year")
            mo = _MONTHS.get(month_name)
            if mo is None:
                continue
            if year_raw:
                try:
                    candidates.append(date(int(year_raw), mo, day))
                except ValueError:
                    continue
            else:
                # Try this year; if it's in the future, fall back to last year.
                for y in (today.year, today.year - 1):
                    try:
                        cand = date(y, mo, day)
                    except ValueError:
                        continue
                    if cand <= today:
                        candidates.append(cand)
                        break
    if not candidates:
        return None
    return max(candidates)


def parse_planning_row(
    row: list[str],
    headers: list[str],
    strategist_email: str,
    *,
    today: date | None = None,
) -> tuple[ParsedRow | None, RejectRow | None, dict[str, int]]:
    """Parse one Focused Acct Planning row.

    Headers: Customer | Type | Actionable Outcome | AE | FY | Quarter | Date
            | Related documents | Outcomes / Next Steps
    """
    stats_inc: dict[str, int] = {}
    raw = _row_to_dict(row, headers)
    customer = (raw.get("Customer") or "").strip()
    if not customer:
        return None, None, stats_inc

    session_date = parse_date(raw.get("Date"))
    if session_date is None and (raw.get("Date") or "").strip():
        return None, RejectRow(
            original_row_json=json.dumps(raw),
            reason=f"focused_account_planning: unparseable date {raw.get('Date')!r}",
        ), stats_inc

    planning_type = (raw.get("Type") or "").strip() or None
    if planning_type and planning_type not in PLANNING_TYPES:
        stats_inc["unknown_planning_type"] = stats_inc.get("unknown_planning_type", 0) + 1

    fy_raw = (raw.get("FY") or "").strip() or None
    fy = fy_raw or derive_fy_from_date(session_date)
    quarter = normalize_quarter(raw.get("Quarter"), session_date, fy)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    parsed = ParsedRow(
        fields=dict(
            strategist_email=strategist_email,
            customer=customer,
            account_id=None,  # Sheet has no account_id column; populated later.
            planning_type=planning_type,
            actionable_outcome=(raw.get("Actionable Outcome") or "").strip() or None,
            ae=(raw.get("AE") or "").strip() or None,
            fy=fy,
            quarter=quarter,
            session_date=session_date,
            related_documents=(raw.get("Related documents") or "").strip() or None,
            asq_id=None,  # Sheet has no asq_id column; reconciled later in Mode D.
            next_steps=(raw.get("Outcomes / Next Steps") or "").strip() or None,
            created_at=now,
            updated_at=now,
        )
    )
    return parsed, None, stats_inc


def parse_exec_meeting_row(
    row: list[str],
    headers: list[str],
    strategist_email: str,
    *,
    today: date | None = None,
) -> tuple[ParsedRow | None, RejectRow | None, dict[str, int]]:
    """Parse one Exec Meeting row.

    Headers: Customer | Title | Name | CXO | Objective | Outcome | Date
    """
    stats_inc: dict[str, int] = {}
    raw = _row_to_dict(row, headers)
    customer = (raw.get("Customer") or "").strip()
    exec_name = (raw.get("Name") or "").strip()
    if not customer and not exec_name:
        return None, None, stats_inc

    meeting_date = parse_date(raw.get("Date"))
    if meeting_date is None and (raw.get("Date") or "").strip():
        return None, RejectRow(
            original_row_json=json.dumps(raw),
            reason=f"exec_meetings: unparseable date {raw.get('Date')!r}",
        ), stats_inc

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    parsed = ParsedRow(
        fields=dict(
            strategist_email=strategist_email,
            customer=customer or None,
            account_id=None,
            exec_name=exec_name or None,
            exec_title=(raw.get("Title") or "").strip() or None,
            is_cxo=parse_cxo_bool(raw.get("CXO")),
            objective=(raw.get("Objective") or "").strip() or None,
            outcome=(raw.get("Outcome") or "").strip() or None,
            meeting_date=meeting_date,
            asq_id=None,
            evangelism_id=None,
            initiative_id=None,
            context=None,
            created_at=now,
            updated_at=now,
        )
    )
    return parsed, None, stats_inc


PARSER_BY_TAB = {
    "evangelism": parse_evangelism_row,
    "initiatives": parse_initiative_row,
    "focused_account_planning": parse_planning_row,
    "exec_meetings": parse_exec_meeting_row,
}


# -------------------------------------------------------------------------- #
# Parquet staging
# -------------------------------------------------------------------------- #


def rows_to_dataframe(rows: list[ParsedRow]) -> pd.DataFrame:
    """Build a DataFrame from parsed rows with consistent column order."""
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([r.fields for r in rows])


def write_parquet(df: pd.DataFrame, local_path: Path) -> None:
    """Write the DataFrame to local Parquet. Pyarrow is required."""
    local_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(local_path, engine="pyarrow", index=False)


def upload_parquet_to_volume(local_path: Path, volume_path: str) -> None:
    """Upload `local_path` to `volume_path` via the Databricks Files API.

    Uses `databricks-sdk`'s `w.files.upload`. Folder is auto-created.
    """
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    with local_path.open("rb") as fh:
        w.files.upload(volume_path, fh, overwrite=True)


# -------------------------------------------------------------------------- #
# MERGE layer (only invoked under --apply)
# -------------------------------------------------------------------------- #


def _sql_conn(warehouse_id: str):
    """Open a databricks-sql-connector connection. Imported lazily so tests
    don't require the connector to import this module."""
    from databricks import sql as dbsql

    host = (os.environ.get("DATABRICKS_HOST") or "").replace("https://", "").rstrip("/")
    token = os.environ.get("DATABRICKS_TOKEN")
    if not host or not token:
        raise RuntimeError("DATABRICKS_HOST and DATABRICKS_TOKEN must be set for --apply")
    return dbsql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{warehouse_id}",
        access_token=token,
    )


def detect_natural_key_collisions(df: pd.DataFrame, tab: str) -> pd.DataFrame:
    """Return rows whose natural keys collide (more than one parsed row per key).

    Two rows with the same natural key but different secondary fields are
    a migration smell — see test_migration_natural_key_collision.
    """
    if df.empty:
        return df
    keys = list(NATURAL_KEYS[tab])
    grouped = df.groupby(keys, dropna=False).size().reset_index(name="_count")
    colliding_keys = grouped[grouped["_count"] > 1].drop(columns=["_count"])
    if colliding_keys.empty:
        return colliding_keys
    return df.merge(colliding_keys, on=keys, how="inner")


def build_merge_sql(tab: str, staged_volume_path: str) -> str:
    """Build a single MERGE INTO statement that reads the staged parquet.

    Uses `read_files()` on the volume path — no temp tables, no Spark
    session required from the script side.
    """
    target = TARGET_TABLE[tab]
    keys = NATURAL_KEYS[tab]
    on_clauses = " AND ".join(f"t.{k} <=> s.{k}" for k in keys)

    # `set_clause` updates every non-key column on conflict. We do NOT touch
    # `id` (IDENTITY) or `created_at`. `updated_at` gets bumped to now.
    table_to_cols = {
        "evangelism": [
            "event_type", "title", "event_date", "location", "fy", "quarter",
            "resources", "participants", "views", "comments", "status",
            "next_steps",
        ],
        "initiatives": [
            "feip_ticket", "actionable_outcome", "resources", "status", "fy",
            "next_steps", "last_activity_at",
        ],
        "focused_account_planning": [
            "account_id", "planning_type", "actionable_outcome", "ae", "fy",
            "quarter", "related_documents", "asq_id", "next_steps",
        ],
        "exec_meetings": [
            "account_id", "exec_title", "is_cxo", "objective", "outcome",
            "asq_id", "evangelism_id", "initiative_id", "context",
        ],
    }
    update_cols = table_to_cols[tab]
    insert_cols = list(keys) + update_cols + ["created_at", "updated_at"]
    set_assignments = ", ".join(f"t.{c} = s.{c}" for c in update_cols)
    set_assignments += ", t.updated_at = current_timestamp()"
    insert_col_list = ", ".join(insert_cols)
    insert_val_list = ", ".join(
        "current_timestamp()" if c in ("created_at", "updated_at") else f"s.{c}"
        for c in insert_cols
    )

    return f"""
    MERGE INTO {target} t
    USING (SELECT * FROM read_files('{staged_volume_path}', format => 'parquet')) s
    ON {on_clauses}
    WHEN MATCHED THEN UPDATE SET {set_assignments}
    WHEN NOT MATCHED THEN INSERT ({insert_col_list}) VALUES ({insert_val_list})
    """.strip()


def execute_merge(tab: str, staged_volume_path: str, *, warehouse_id: str) -> dict[str, int]:
    """Run MERGE INTO via SQL warehouse. Returns operational counts when
    available (Delta's MERGE doesn't always return them via the JDBC layer —
    in that case we infer via a count diff)."""
    target = TARGET_TABLE[tab]
    sql = build_merge_sql(tab, staged_volume_path)

    with _sql_conn(warehouse_id) as conn, conn.cursor() as cur:
        # Pre-count for diff inference.
        cur.execute(f"SELECT COUNT(*) FROM {target}")
        before = cur.fetchone()[0]
        cur.execute(sql)
        cur.execute(f"SELECT COUNT(*) FROM {target}")
        after = cur.fetchone()[0]

    # We can compute inserts via the count diff; updates are harder without
    # parsing MERGE's operation_metrics. Surface what we know honestly.
    return {"rows_before": before, "rows_after": after, "inserts_inferred": after - before}


# -------------------------------------------------------------------------- #
# Report
# -------------------------------------------------------------------------- #


def write_report(stats: list[TabStats], report_path: Path, applied: bool) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Strategist activity migration — {date.today().isoformat()}",
        "",
        f"Mode: **{'apply' if applied else 'dry-run'}**",
        "",
        "| Tab | Rows read | Parsed | Rejected | Notes |",
        "|---|---:|---:|---:|---|",
    ]
    for s in stats:
        note_str = "; ".join(s.notes) if s.notes else ""
        lines.append(
            f"| {s.tab} | {s.rows_read} | {s.rows_parsed} | {s.rows_rejected} | {note_str} |"
        )
        if s.comments_text_dropped:
            lines.append(
                f"|   ↳ comments_text_dropped (evangelism) |  |  |  | "
                f"{s.comments_text_dropped} text comments parsed as NULL |"
            )
    report_path.write_text("\n".join(lines) + "\n")


# -------------------------------------------------------------------------- #
# Orchestrator
# -------------------------------------------------------------------------- #


def migrate_tab(
    tab: str,
    *,
    strategist_email: str,
    staging_dir: Path,
    rejects_path: Path | None,
    apply: bool,
    warehouse_id: str,
    sheet_rows: list[list[str]] | None = None,
    auth_script: str,
    user_project: str,
    allow_conflict: bool = False,
    today: date | None = None,
) -> TabStats:
    """Migrate a single tab end-to-end. `sheet_rows` is injectable for tests."""
    stats = TabStats(tab=tab)

    if sheet_rows is None:
        tab_title, sheet_range = TAB_RANGES[tab]
        sheet_rows = read_sheet_tab(
            tab_title, sheet_range, auth_script=auth_script, user_project=user_project
        )

    if not sheet_rows:
        stats.notes.append("empty tab")
        return stats

    headers = sheet_rows[0]
    body = sheet_rows[1:]
    stats.rows_read = len(body)

    parser = PARSER_BY_TAB[tab]
    parsed_rows: list[ParsedRow] = []
    reject_rows: list[RejectRow] = []
    aggregated_inc: dict[str, int] = {}
    for r in body:
        parsed, reject, inc = parser(r, headers, strategist_email, today=today)
        if reject is not None:
            reject_rows.append(reject)
        if parsed is not None:
            parsed_rows.append(parsed)
        for k, v in inc.items():
            aggregated_inc[k] = aggregated_inc.get(k, 0) + v

    stats.rows_parsed = len(parsed_rows)
    stats.rows_rejected = len(reject_rows)
    stats.comments_text_dropped = aggregated_inc.get("comments_text_dropped", 0)
    if aggregated_inc.get("unknown_event_type"):
        stats.notes.append(f"{aggregated_inc['unknown_event_type']} unknown event_type(s)")
    if aggregated_inc.get("unknown_planning_type"):
        stats.notes.append(f"{aggregated_inc['unknown_planning_type']} unknown planning_type(s)")

    # Stage parsed rows as parquet.
    df = rows_to_dataframe(parsed_rows)
    today_str = date.today().isoformat()
    local_parquet = staging_dir / f"{tab}_{today_str}.parquet"
    if not df.empty:
        write_parquet(df, local_parquet)

    # Detect natural-key collisions BEFORE merge (regardless of apply).
    collisions = detect_natural_key_collisions(df, tab)
    if not collisions.empty and not allow_conflict:
        stats.notes.append(
            f"{len(collisions)} rows hit natural-key collision; "
            "merge skipped (use --allow-conflict to override)"
        )
        # Surface as a soft reject for visibility.
        for _, r in collisions.iterrows():
            reject_rows.append(
                RejectRow(
                    original_row_json=r.to_json(default_handler=str),
                    reason="natural_key_collision",
                )
            )
        stats.rows_rejected = len(reject_rows)
        # Drop the collision rows so apply mode does not propagate them.
        keys = list(NATURAL_KEYS[tab])
        collision_keys = collisions[keys].drop_duplicates()
        df = (
            df.merge(collision_keys, on=keys, how="left", indicator=True)
            .query("_merge == 'left_only'")
            .drop(columns=["_merge"])
        )
        if not df.empty:
            write_parquet(df, local_parquet)

    # Write rejects (always, even if empty — gives the reviewer one path to inspect).
    if rejects_path is None:
        rejects_local = staging_dir / f"{tab}_rejects_{today_str}.parquet"
    else:
        rejects_local = rejects_path
    rejects_df = pd.DataFrame(
        [{"original_row_json": r.original_row_json, "reason": r.reason} for r in reject_rows]
    )
    if not rejects_df.empty:
        write_parquet(rejects_df, rejects_local)

    # Upload to UC volume.
    staged_volume_path = f"{DEFAULT_STAGING_VOLUME}/{tab}_{today_str}.parquet"
    if not df.empty and apply:
        upload_parquet_to_volume(local_parquet, staged_volume_path)
        if not rejects_df.empty:
            rejects_volume_path = f"{DEFAULT_STAGING_VOLUME}/{tab}_rejects_{today_str}.parquet"
            upload_parquet_to_volume(rejects_local, rejects_volume_path)
        merge_result = execute_merge(tab, staged_volume_path, warehouse_id=warehouse_id)
        stats.notes.append(
            f"MERGE: before={merge_result['rows_before']} "
            f"after={merge_result['rows_after']} "
            f"inserts_inferred={merge_result['inserts_inferred']}"
        )
    elif not df.empty:
        # Dry-run path: still upload the staged parquet so reviewer can
        # inspect via the volume browser, but do NOT MERGE.
        try:
            upload_parquet_to_volume(local_parquet, staged_volume_path)
            stats.notes.append(f"dry-run staged → {staged_volume_path}")
        except Exception as e:  # noqa: BLE001
            stats.notes.append(f"dry-run upload skipped ({type(e).__name__})")
            logger.warning("Volume upload failed in dry-run for %s: %s", tab, e)

    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tab",
        choices=("evangelism", "initiatives", "focused_account_planning", "exec_meetings", "all"),
        required=True,
    )
    mode_grp = parser.add_mutually_exclusive_group()
    mode_grp.add_argument("--dry-run", action="store_true", default=True)
    mode_grp.add_argument("--apply", action="store_true", default=False)
    parser.add_argument("--rejects-path", type=Path, default=None)
    parser.add_argument("--allow-conflict", action="store_true", default=False)
    parser.add_argument("--strategist-email", default=os.environ.get("STRATEGIST_EMAIL", DEFAULT_STRATEGIST_EMAIL))
    parser.add_argument(
        "--warehouse-id",
        default=os.environ.get("DATABRICKS_WAREHOUSE_ID", DEFAULT_WAREHOUSE_ID),
    )
    parser.add_argument(
        "--auth-script",
        default=os.environ.get("GOOGLE_AUTH_SCRIPT", DEFAULT_GOOGLE_AUTH),
    )
    parser.add_argument(
        "--user-project",
        default=os.environ.get("GOOGLE_USER_PROJECT", DEFAULT_GOOGLE_USER_PROJECT),
    )
    parser.add_argument("--report-path", type=Path, default=None)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(level=args.log_level, format="%(levelname)s %(name)s: %(message)s")
    applied = args.apply  # --dry-run is the default; --apply overrides.

    tabs = (
        ["evangelism", "initiatives", "focused_account_planning", "exec_meetings"]
        if args.tab == "all"
        else [args.tab]
    )

    staging_dir = Path(tempfile.mkdtemp(prefix="strategist_activity_"))
    logger.info("Staging local parquet under %s", staging_dir)

    all_stats: list[TabStats] = []
    for tab in tabs:
        logger.info("Migrating tab=%s apply=%s", tab, applied)
        stats = migrate_tab(
            tab,
            strategist_email=args.strategist_email,
            staging_dir=staging_dir,
            rejects_path=args.rejects_path,
            apply=applied,
            warehouse_id=args.warehouse_id,
            auth_script=args.auth_script,
            user_project=args.user_project,
            allow_conflict=args.allow_conflict,
        )
        all_stats.append(stats)

    today_str = date.today().isoformat()
    report_path = args.report_path or Path(f"/tmp/migration_{today_str}.md")
    write_report(all_stats, report_path, applied)
    logger.info("Report written → %s", report_path)
    print(report_path.read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
