from services.incident_analysis import (
    REASON_CARRIER,
    REASON_CUSTOMER_EMAIL,
    REASON_CUSTOMER_TYPE,
    REASON_DATE,
    REASON_DUPLICATE_INCIDENT_ID,
    REASON_INCIDENT_ID,
    REASON_STATUS,
    REASON_TRACKING_NUMBER,
    analyze_incidents,
    validate_incident,
)


def valid_row(**overrides: str) -> dict[str, str]:
    row = {
        "incident_id": "TRF-000001",
        "date": "2026-01-01",
        "country": "US",
        "customer_type": "B2C",
        "tracking_number": "TRACK1234",
        "carrier": "UPS",
        "category": "DAMAGE",
        "description": "Package arrived damaged",
        "status": "CLOSED",
        "customer_email": "customer@example.test",
        "satisfaction_score": "4",
    }
    row.update(overrides)
    return row


def test_validation_returns_multiple_reasons_without_email() -> None:
    result = validate_incident(
        valid_row(country="ES", carrier="UPS", tracking_number="short", customer_email="")
    )

    assert not result.valid
    assert REASON_CARRIER in result.reasons
    assert REASON_TRACKING_NUMBER in result.reasons
    assert REASON_CUSTOMER_EMAIL in result.reasons
    assert "customer@example.test" not in repr(result)


def test_invalid_rows_are_excluded_from_all_metrics() -> None:
    report = analyze_incidents(
        [
            valid_row(),
            valid_row(incident_id="TRF-000002", category="LOST_PARCEL", status="OPEN", satisfaction_score=""),
            valid_row(incident_id="TRF-000003", tracking_number="bad"),
        ]
    )

    assert report.total_records == 3
    assert report.valid_records == 2
    assert report.invalid_records == 1
    assert report.category_breakdown["DAMAGE"] == 1
    assert report.category_breakdown["LOST_PARCEL"] == 1
    assert report.score_distribution == {1: 0, 2: 0, 3: 0, 4: 1, 5: 0}
    assert report.invalid_by_reason[REASON_TRACKING_NUMBER] == 1


def test_schema_fields_are_validated() -> None:
    invalid = validate_incident(
        valid_row(
            incident_id="INC-1",
            date="2026-02-30",
            customer_type="RETAIL",
            status="PENDING",
        )
    )

    assert not invalid.valid
    assert {REASON_INCIDENT_ID, REASON_DATE, REASON_CUSTOMER_TYPE, REASON_STATUS}.issubset(
        invalid.reasons
    )


def test_duplicate_incident_id_invalidates_later_record() -> None:
    report = analyze_incidents([valid_row(), valid_row(category="LOST_PARCEL")])

    assert report.valid_records == 1
    assert report.invalid_records == 1
    assert report.invalid_by_reason[REASON_DUPLICATE_INCIDENT_ID] == 1


def test_missing_required_fields_and_multiple_reasons_are_safe() -> None:
    invalid = validate_incident(
        {"incident_id": "bad", "country": "ES", "carrier": "UPS", "customer_email": "secret@example.test"}
    )

    assert not invalid.valid
    assert len(invalid.reasons) >= 7
    assert "secret@example.test" not in repr(invalid)
