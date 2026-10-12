"""Tests of the period rule in all_facts.py (spec Acceptance 3b).

    python -m pytest -q -p no:cacheprovider docs/superpowers/audits/2026-10-11-xlsx-header-detection/test_all_facts.py

The mismatch cases are the blind spots of Task 3's scratch checker: it accepted
any duration starting within a day of the header date, under any header, and
read `Quarter ended` as a bare date.
"""

from all_facts import period_verdict


def duration(start, end):
    return ['D', start, end, False]


def instant(date):
    return ['I', None, date, False]


def test_six_months_under_three_months_header_is_mismatch():
    assert period_verdict(duration('2025-01-01', '2025-06-30'), 'Three Months Ended June 30, 2025') == 'mismatch'


def test_starting_day_after_three_months_header_date_is_mismatch():
    assert period_verdict(duration('2025-04-01', '2025-06-30'), 'Three Months Ended March 31, 2025') == 'mismatch'


def test_six_months_under_quarter_ended_header_is_mismatch():
    assert period_verdict(duration('2025-01-01', '2025-06-30'), 'Quarter ended June 30, 2025') == 'mismatch'


def test_starting_day_after_bare_date_is_ok():
    assert period_verdict(duration('2025-01-01', '2025-12-31'), 'December 31, 2024') == 'ok'


def test_starting_on_bare_date_is_mismatch():
    assert period_verdict(duration('2024-12-31', '2025-12-31'), 'December 31, 2024') == 'mismatch'


def test_starting_day_before_bare_date_is_mismatch():
    assert period_verdict(duration('2024-12-30', '2025-12-31'), 'December 31, 2024') == 'mismatch'


def test_opening_balance_at_start_of_three_months_is_ok():
    assert period_verdict(instant('2024-12-31'), 'Three Months Ended March 31, 2025') == 'ok'


def test_three_months_under_three_months_header_is_ok():
    assert period_verdict(duration('2025-01-01', '2025-03-31'), 'Three Months Ended March 31, 2025') == 'ok'
