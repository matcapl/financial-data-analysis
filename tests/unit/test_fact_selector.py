"""Unit tests for fact selection helpers."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "server"))

from app.services.fact_selector import parse_number


def test_parse_number_parses_currency_and_commas():
    assert parse_number("£1,234") == 1234.0
    assert parse_number("(1,234)") == -1234.0


def test_parse_number_handles_blanks():
    assert parse_number("") is None
    assert parse_number(None) is None
    assert parse_number("—") is None
