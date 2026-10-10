# CONTEXT — Supplier Directory · TrackFlow

> **Milestone:** 09 — Lightweight Storage API
>
> This file is the supplier-directory context used by the API, seeder, and backoffice page. It records the TrackFlow brief supplied for this milestone. A Spanish companion file was not part of that drop.

## Company

TrackFlow Tech is the internal technology unit of TrackFlow, a last-mile logistics and warehouse company with operations in Los Angeles (USA) and Zaragoza (Spain). The directory unifies the supplier spreadsheets kept separately for each country.

## Supplier model

| Field | Type | Description |
| --- | --- | --- |
| `name` | string, required | Supplier trade name |
| `country` | string, required | `"USA"` or `"Spain"` |
| `categories` | list of strings, required, minimum 1 | Service or product supplied |
| `rate_per_shipment` | float, required, > 0 | Current rate per shipment or service unit in the contract currency |
| `currency` | string, required | `"USD"` for USA, `"EUR"` for Spain |
| `updated_at` | datetime, system-generated | Timestamp of the last rate update |
| `status` | string, required | `"active"` or `"suspended"` |
| `service_zone` | string, optional | Coverage zone |
| `contact_email` | string, optional | Supplier contact email |
| `notes` | string, optional | Operations notes |

### Valid categories

`carrier_last_mile`, `carrier_international`, `warehouse_supplies`, `packaging_materials`, `reverse_logistics`, `fleet_maintenance`, `it_and_wms_software`, `cleaning_and_facilities`

### Valid statuses

`active`, `suspended`

### Business constraints

- A supplier from `"USA"` must use `currency = "USD"`. A supplier from `"Spain"` must use `currency = "EUR"`.
- Every change to `rate_per_shipment` records a new server `updated_at`. A status change does not.
- A carrier may have more than one category at the same time.
- Suspension is the operational alternative to deletion.

## Seeder initial data

The seeder loads these 15 suppliers. The natural key is the normalized name plus country. Repeated runs insert only missing keys and do not overwrite an existing rate or status.

| Name | Country | Categories | Rate | Currency | Status |
| --- | --- | --- | --- | --- | --- |
| UPS Ground | USA | carrier_last_mile | 7.45 | USD | active |
| FedEx Ground | USA | carrier_last_mile | 7.90 | USD | active |
| DHL Express USA | USA | carrier_last_mile, carrier_international | 14.20 | USD | active |
| OnTrac | USA | carrier_last_mile | 6.10 | USD | active |
| Laser Ship | USA | carrier_last_mile | 5.80 | USD | suspended |
| PackSource LA | USA | packaging_materials | 0.42 | USD | active |
| CleanTeam West | USA | cleaning_and_facilities | 1800.0 | USD | active |
| MRW España | Spain | carrier_last_mile | 4.90 | EUR | active |
| SEUR | Spain | carrier_last_mile | 5.20 | EUR | active |
| DHL Express España | Spain | carrier_last_mile, carrier_international | 12.80 | EUR | active |
| Nacex | Spain | carrier_last_mile | 4.60 | EUR | active |
| Logística Inversa Iberia | Spain | reverse_logistics | 6.30 | EUR | active |
| Embalajes Zaragoza S.L. | Spain | packaging_materials | 0.28 | EUR | active |
| SAP WM Cloud | USA | it_and_wms_software | 2200.0 | USD | suspended |
| ReturnBear | USA | reverse_logistics | 4.15 | USD | active |

Optional zone, email, and notes for each record are stored in `services/api/seed.py` and match the assigned seed list.
