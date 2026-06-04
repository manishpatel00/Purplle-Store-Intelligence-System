# PROMPT: Unit tests for POS order parsing and store_id mapping (ST1008 -> STORE_BLR_002)
# CHANGES MADE: Added date parsing and store filter tests without DB.

from datetime import date

from app.pos import _parse_order_datetime, load_pos_orders, orders_for_date


def test_parse_order_datetime():
    ts = _parse_order_datetime("10-04-2026", "12:42:18")
    assert ts is not None
    assert ts.date() == date(2026, 4, 10)
    assert ts.hour == 12 and ts.minute == 42


def test_orders_for_date_filters_store():
    import os

    path = os.path.join(os.path.dirname(__file__), "fixtures", "pos_correlation.csv")
    orders = load_pos_orders(path)
    blr = orders_for_date(orders, date(2026, 4, 10), "STORE_BLR_002")
    other = orders_for_date(orders, date(2026, 4, 10), "STORE_OTHER_999")
    assert len(blr) == 2
    assert len(other) == 0
