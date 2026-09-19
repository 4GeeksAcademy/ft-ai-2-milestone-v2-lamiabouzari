from datetime import date
import os

os.environ.setdefault("JWT_SECRET", "test-only-validation-secret")

from data.pipelines.pipeline import transform_warehouse_client_kpis


WEEK_START = date(2026, 9, 14)


def transform(events: list[dict]) -> list[dict]:
    """Call the Prefect task's business logic without starting a flow."""
    return transform_warehouse_client_kpis.fn(events, WEEK_START)


def test_hand_calculated_kpis() -> None:
    events = [
        {"event_type": "inbound_order_created", "tags": {"warehouse": "W1", "client_id": "C1", "quantity": 10}},
        {"event_type": "outbound_order_created", "tags": {"warehouse": "W1", "client_id": "C1"}},
        {"event_type": "outbound_order_created", "tags": {"warehouse": "W1", "client_id": "C1"}},
        {"event_type": "outbound_order_created", "tags": {"warehouse": "W1", "client_id": "C1"}},
        {"event_type": "outbound_order_created", "tags": {"warehouse": "W1", "client_id": "C1"}},
        {"event_type": "stock_threshold_triggered", "tags": {"warehouse": "W1", "client_id": "C1"}},
        {"event_type": "inventory_discrepancy_detected", "tags": {"warehouse": "W1", "client_id": "C1"}},
        {"event_type": "inventory_discrepancy_detected", "tags": {"warehouse": "W1", "client_id": "C1"}},
    ]

    assert transform(events) == [
        {
            "warehouse": "W1",
            "client_id": "C1",
            "week_start": WEEK_START,
            "inbound_units_count": 10,
            "outbound_orders_count": 4,
            "stockout_events_count": 1,
            "discrepancy_events_count": 2,
            "discrepancy_rate": 0.5,  # 2 discrepancies / 4 outbound orders
            "week_end": date(2026, 9, 21),
        }
    ]


def test_multiple_warehouse_client_groups_are_separate() -> None:
    events = [
        {"event_type": "inbound_order_created", "tags": {"warehouse": "W1", "client_id": "C1", "quantity": 3}},
        {"event_type": "outbound_order_created", "tags": {"warehouse": "W1", "client_id": "C1"}},
        {"event_type": "inbound_order_created", "tags": {"warehouse": "W2", "client_id": "C2", "quantity": 7}},
        {"event_type": "stock_threshold_triggered", "tags": {"warehouse": "W2", "client_id": "C2"}},
    ]

    rows = transform(events)

    assert {(row["warehouse"], row["client_id"]) for row in rows} == {
        ("W1", "C1"),
        ("W2", "C2"),
    }
    assert next(row for row in rows if row["warehouse"] == "W1")["inbound_units_count"] == 3
    assert next(row for row in rows if row["warehouse"] == "W2")["stockout_events_count"] == 1


def test_malformed_or_missing_group_tags_are_skipped() -> None:
    events = [
        {"event_type": "outbound_order_created", "tags": {"client_id": "C1"}},
        {"event_type": "outbound_order_created", "tags": {"warehouse": "W1"}},
        {"event_type": "outbound_order_created", "tags": {"warehouse": "", "client_id": "C2"}},
        {"event_type": "outbound_order_created", "tags": {"warehouse": "W2", "client_id": None}},
        {"event_type": "outbound_order_created", "tags": "not-json"},
        {"event_type": "outbound_order_created", "tags": {"warehouse": "W3", "client_id": "C3"}},
    ]

    rows = transform(events)

    assert rows == [
        {
            "warehouse": "W3",
            "client_id": "C3",
            "week_start": WEEK_START,
            "inbound_units_count": 0,
            "outbound_orders_count": 1,
            "stockout_events_count": 0,
            "discrepancy_events_count": 0,
            "discrepancy_rate": 0,
            "week_end": date(2026, 9, 21),
        }
    ]


def test_zero_outbound_orders_have_zero_discrepancy_rate() -> None:
    events = [
        {"event_type": "inbound_order_created", "tags": {"warehouse": "W1", "client_id": "C1", "quantity": 4}},
        {"event_type": "inventory_discrepancy_detected", "tags": {"warehouse": "W1", "client_id": "C1"}},
    ]

    row = transform(events)[0]

    assert row["outbound_orders_count"] == 0
    assert row["discrepancy_events_count"] == 1
    assert row["discrepancy_rate"] == 0
