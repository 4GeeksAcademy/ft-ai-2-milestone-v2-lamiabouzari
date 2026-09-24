# Background processes

## Nightly telemetry export

Run the exporter independently from the API process with OS cron. For a
production deployment that runs at 02:00 UTC every day:

```cron
0 2 * * * cd /path/to/repo && /usr/bin/python scripts/nightly_export.py >> /var/log/nightly_export.log 2>&1
```

The command is equivalent to:

```text
python -m data.pipelines.pipeline --triggered-by nightly_export
```

OS cron was chosen because it keeps the nightly process independent of
FastAPI's main thread and request lifecycle. The scheduler is not embedded in
FastAPI, so restarting or scaling the API does not create duplicate schedulers.

Set `TARGET_DATE=YYYY-MM-DD` for an explicit UTC calendar day when replaying or
backfilling a snapshot.
