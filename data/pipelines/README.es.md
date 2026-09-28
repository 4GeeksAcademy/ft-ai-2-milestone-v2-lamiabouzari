# Carpeta `data/pipelines`

Esta carpeta agrupa **todos los pipelines de datos del monorepo** relacionados con la compañía: procesos de ingesta, ETL/ELT, limpieza, transformación y carga hacia sistemas analíticos o de producción.

Cada subcarpeta o archivo dentro de `data/pipelines/` debe representar **un pipeline o conjunto de jobs** (por ejemplo `sales-etl`, `telemetry-stream`, `customer-segmentation`) e incluir la configuración necesaria (scripts, orquestación, conectores, esquemas, etc.).

- **Propósito principal**: unificar en un único lugar la lógica de movimiento y transformación de datos que soporta las aplicaciones y analíticas de la compañía.
- **Recomendación**: documenta aquí los pipelines que vayas añadiendo, describiendo su objetivo, orígenes/destinos de datos, dependencias y cómo ejecutarlos en desarrollo, pruebas y producción.

## Pipelines en esta carpeta

| Pipeline | Archivo | Descripción |
| --- | --- | --- |
| KPIs semanales de almacén/cliente | `pipeline.py` | Tarea Prefect que agrega los KPIs semanales por almacén/cliente a partir de eventos de telemetría. |
| Previsión de ventas | `sales_forecasting.py` | Previsión de ingresos mensuales de TrackFlow: carga/valida `data/raw/trackflow_sales.csv`, división cronológica 8 años entrenamiento / 2 años test, características causales (lags, rolling, calendario), Random Forest (`random_state=42`), métricas MSE/PSI/Gini/K2 en el periodo de test y gráfico de previsión 2024-2025. Ejecutar con `python scripts/train_sales_forecast.py`. Documentación: `docs/sales-forecasting.md`. Tests: `tests/pipelines/test_sales_forecast.py`. |
