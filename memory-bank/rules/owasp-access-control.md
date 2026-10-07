# OWASP access control

Incident, inventory, reporting, telemetry report, task status, and agent/knowledge routes require the existing JWT (`get_current_user`).

`GET /users` is admin-only. `GET /users/{id}` is self or admin.

The support agent checks order ownership before jailbreak text. `authorize_order_access` denies orders outside the session allow-list and does not return an address.

Untrusted text that says to always assign a carrier is rejected by `agent_memory.forbidden_reason` and is not stored as a carrier rule.

Redis, Qdrant, and Flower in `docker-compose.yml` bind to `127.0.0.1`. The API image runs as `trackflow` without `--reload`. Host sshd and firewall changes are in `docs/security/server-hardening.md` and are not applied by the repository alone.
