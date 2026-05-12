"""T-217: pure-function tests for the sheet migration parsers.

Covers the five parser categories called out in the spec:
- date parser (5 input shapes + garbage)
- quarter normalizer (FYxxQn, FYxx-Qn, bare Qn, derived)
- evangelism status marker
- initiative status marker
- CXO boolean

All tests are network-free.
"""

from __future__ import annotations

from datetime import date

from scripts.migrate_strategist_activity_from_sheet import (
    _extract_latest_dated_bullet,
    clean_initiative_name,
    derive_fy_from_date,
    derive_quarter_from_date,
    normalize_quarter,
    parse_cxo_bool,
    parse_date,
    parse_evangelism_status,
    parse_initiative_status,
    parse_int,
)


class TestParseDate:
    def test_german_ddmmyyyy(self):
        assert parse_date("25.04.2025") == date(2025, 4, 25)

    def test_german_with_single_digits(self):
        assert parse_date("8.5.2025") == date(2025, 5, 8)

    def test_us_mdyyyy(self):
        assert parse_date("6/15/2024") == date(2024, 6, 15)

    def test_english_full_month(self):
        assert parse_date("6 June 2024") == date(2024, 6, 6)

    def test_english_short_month_with_period(self):
        # The sheet sometimes uses "Sept." with a trailing period.
        assert parse_date("17 Sept. 2024") == date(2024, 9, 17)

    def test_english_short_month_sept(self):
        assert parse_date("17 Sept 2024") == date(2024, 9, 17)

    def test_iso(self):
        assert parse_date("2025-04-25") == date(2025, 4, 25)

    def test_garbage_returns_none(self):
        assert parse_date("not a date at all") is None
        assert parse_date("") is None
        assert parse_date(None) is None

    def test_invalid_calendar_date(self):
        assert parse_date("31.02.2025") is None  # Feb 31 doesn't exist

    def test_whitespace_stripped(self):
        assert parse_date("  6 June 2024  ") == date(2024, 6, 6)


class TestDeriveFY:
    def test_feb_2025_is_fy26(self):
        # FY26 = Feb 2025 – Jan 2026.
        assert derive_fy_from_date(date(2025, 2, 1)) == "FY26"

    def test_jan_2026_is_fy26(self):
        assert derive_fy_from_date(date(2026, 1, 31)) == "FY26"

    def test_feb_2026_is_fy27(self):
        assert derive_fy_from_date(date(2026, 2, 1)) == "FY27"

    def test_none(self):
        assert derive_fy_from_date(None) is None


class TestQuarterNormalizer:
    def test_canonical(self):
        assert normalize_quarter("FY26Q1") == "FY26Q1"

    def test_hyphenated(self):
        assert normalize_quarter("FY26-Q1") == "FY26Q1"

    def test_lowercase(self):
        assert normalize_quarter("fy26q1") == "FY26Q1"

    def test_bare_q_with_fy_hint(self):
        assert normalize_quarter("Q2", fy_hint="FY26") == "FY26Q2"

    def test_bare_q_derived_from_date(self):
        # Feb 2025 → FY26Q1; bare Q2 with no fy_hint but a Feb 2025 date →
        # uses derive_fy_from_date which gives FY26 → FY26Q2 (override).
        assert normalize_quarter("Q2", d=date(2025, 2, 1)) == "FY26Q2"

    def test_empty_derives_from_date(self):
        # No raw value → use derive_quarter_from_date(d).
        assert normalize_quarter("", d=date(2025, 6, 15)) == "FY26Q2"

    def test_empty_no_date(self):
        assert normalize_quarter("") is None
        assert normalize_quarter(None) is None

    def test_garbage(self):
        assert normalize_quarter("garbage") is None


class TestDeriveQuarterFromDate:
    def test_q1_feb(self):
        assert derive_quarter_from_date(date(2025, 2, 1)) == "FY26Q1"

    def test_q1_apr(self):
        assert derive_quarter_from_date(date(2025, 4, 30)) == "FY26Q1"

    def test_q2_may(self):
        assert derive_quarter_from_date(date(2025, 5, 1)) == "FY26Q2"

    def test_q3_aug(self):
        assert derive_quarter_from_date(date(2025, 8, 1)) == "FY26Q3"

    def test_q4_nov(self):
        assert derive_quarter_from_date(date(2025, 11, 1)) == "FY26Q4"

    def test_q4_jan(self):
        assert derive_quarter_from_date(date(2026, 1, 31)) == "FY26Q4"


class TestEvangelismStatusMarker:
    REF_TODAY = date(2026, 5, 12)

    def test_bracket_complete_token(self):
        assert parse_evangelism_status("[complete]", date(2026, 6, 1), today=self.REF_TODAY) == "delivered"

    def test_no_marker_future_date_is_planned(self):
        assert parse_evangelism_status("", date(2026, 6, 1), today=self.REF_TODAY) == "planned"

    def test_no_marker_past_date_is_delivered(self):
        assert parse_evangelism_status("", date(2025, 6, 1), today=self.REF_TODAY) == "delivered"

    def test_literal_token_not_prose(self):
        # "complete the slides" in prose is NOT a delivered marker.
        assert (
            parse_evangelism_status(
                "complete the slides next week", date(2026, 6, 1), today=self.REF_TODAY
            )
            == "planned"
        )

    def test_case_insensitive_bracket(self):
        assert (
            parse_evangelism_status("[COMPLETE]", date(2025, 6, 1), today=self.REF_TODAY)
            == "delivered"
        )

    def test_marker_overrides_future_date(self):
        # Even if the date is in the future, `[complete]` wins.
        assert (
            parse_evangelism_status("[complete]", date(2026, 12, 31), today=self.REF_TODAY)
            == "delivered"
        )


class TestInitiativeStatusMarker:
    def test_on_hold(self):
        assert parse_initiative_status("--- on hold ---\nrest of notes") == "on_hold"

    def test_paused(self):
        assert parse_initiative_status("--- paused ---") == "paused"

    def test_complete(self):
        assert parse_initiative_status("--- complete ---") == "complete"

    def test_no_marker_is_active(self):
        assert parse_initiative_status("[Oct 15] some bullet\n[Sep 25] another") == "active"

    def test_none_is_active(self):
        assert parse_initiative_status(None) == "active"

    def test_mixed_case_marker(self):
        assert parse_initiative_status("--- ON HOLD ---") == "on_hold"

    def test_marker_with_extra_dashes(self):
        # The spec says `--- on hold ---` literal; we accept loose whitespace
        # but require the dash sentinels.
        assert parse_initiative_status("---  on  hold  ---") == "on_hold"


class TestCXOBool:
    def test_true(self):
        assert parse_cxo_bool("TRUE") is True
        assert parse_cxo_bool("true") is True
        assert parse_cxo_bool("True") is True

    def test_one(self):
        assert parse_cxo_bool("1") is True

    def test_false(self):
        assert parse_cxo_bool("FALSE") is False
        assert parse_cxo_bool("false") is False

    def test_zero(self):
        assert parse_cxo_bool("0") is False

    def test_empty(self):
        assert parse_cxo_bool("") is False
        assert parse_cxo_bool(None) is False

    def test_yes_no(self):
        # Accept y/n too — the sheet is hand-entered.
        assert parse_cxo_bool("yes") is True
        assert parse_cxo_bool("no") is False

    def test_unknown_defaults_false(self):
        # Conservative: under-count CXOs rather than inflate.
        assert parse_cxo_bool("maybe") is False


class TestParseInt:
    def test_plain_int(self):
        assert parse_int("800") == 800

    def test_decimal_str(self):
        # Google Sheets sometimes exports "800.0".
        assert parse_int("800.0") == 800

    def test_with_commas(self):
        assert parse_int("1,234,567") == 1_234_567

    def test_empty(self):
        assert parse_int("") is None
        assert parse_int(None) is None

    def test_garbage(self):
        assert parse_int("not a number") is None

    def test_narrative_string(self):
        # The Evangelism "Comments" column often holds prose — confirm we
        # bail to None so the BIGINT column gets NULL not a crash.
        assert parse_int("Very well attended breakout session") is None


class TestCleanInitiativeName:
    def test_strips_link_suffix(self):
        assert clean_initiative_name("Champion Building [link]") == "Champion Building"

    def test_no_suffix(self):
        assert clean_initiative_name("Plain Name") == "Plain Name"

    def test_case_insensitive_suffix(self):
        assert clean_initiative_name("Foo [LINK]") == "Foo"

    def test_whitespace(self):
        assert clean_initiative_name("  Foo [link]  ") == "Foo"


class TestDatedBulletExtractor:
    REF = date(2026, 5, 12)

    def test_picks_most_recent_in_text(self):
        text = "[Sep 25] earlier\n[Oct 15] later"
        # No year → both inferred to 2025 (both in the past relative to ref).
        assert _extract_latest_dated_bullet(text, today=self.REF) == date(2025, 10, 15)

    def test_explicit_year(self):
        text = "[15 Jun 2024] earlier"
        assert _extract_latest_dated_bullet(text, today=self.REF) == date(2024, 6, 15)

    def test_future_dates_roll_back_one_year(self):
        # "Dec 8" in May 2026 → 2025 (since Dec 8 2026 is future).
        text = "[Dec 8] some bullet"
        assert _extract_latest_dated_bullet(text, today=self.REF) == date(2025, 12, 8)

    def test_empty(self):
        assert _extract_latest_dated_bullet(None, today=self.REF) is None
        assert _extract_latest_dated_bullet("", today=self.REF) is None

    def test_no_bullets(self):
        assert _extract_latest_dated_bullet("no dated bullets here", today=self.REF) is None
