# Reference vs. Target

Before editing, confirm which tree you are in. Never overwrite or delete legacy files to “make room” for the new app.

| Path | Role | Rule |
|------|------|------|
| `uis/website_v1/` | Legacy static reference | **Read-only** unless the task explicitly says to change it |
| `uis/website/` (planned) | Next.js target app | All new migration work goes here |
| `packages/shared/` | Shared types & contracts | Extend here; do not duplicate types inside the UI app |
