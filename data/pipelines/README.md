# `data/pipelines` folder

This folder groups **all data pipelines in the monorepo** related to the company: ingestion, ETL/ELT, cleaning, transformation, and loading into analytical or production systems.

Each subfolder or file under `data/pipelines/` should represent **one pipeline or job set** (for example `sales-etl`, `telemetry-stream`, `customer-segmentation`) and include the required configuration (scripts, orchestration, connectors, schemas, etc.).

- **Main purpose**: consolidate in one place the data movement and transformation logic that powers the company’s applications and analytics.
- **Recommendation**: document pipelines as you add them—their goal, data sources and sinks, dependencies, and how to run them in development, testing, and production.

> _Spanish version: [README.es.md](./README.es.md)._

## Pipelines in this folder

| Pipeline | File | Description |
| --- | --- | --- |
| Warehouse client KPIs | `pipeline.py` | Prefect task that aggregates weekly warehouse/client KPIs from telemetry events. |
| Sales forecasting | `sales_forecasting.py` | TrackFlow monthly revenue forecasting: loads/validates `data/raw/trackflow_sales.csv`, chronological 8-year train / 2-year test split, causal lag/rolling/calendar features, Random Forest (`random_state=42`), MSE/PSI/Gini/K2 metrics on the test period, 2024-2025 forecast chart. Run with `python scripts/train_sales_forecast.py`. Full docs: `docs/sales-forecasting.md`. Tests: `tests/pipelines/test_sales_forecast.py`. |
