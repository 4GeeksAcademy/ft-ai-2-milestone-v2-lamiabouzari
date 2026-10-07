# TrackFlow server hardening

This document is a repository runbook. It does not record output from a
production host. Commands under "Deployment verification" must be run on
the real server by an operator. Nothing in this file is a claim that those
commands were executed in this audit.

Public application ports that the compose file publishes for users:

- `3000` website
- `3001` backoffice
- `8000` API

SSH is an operations port and is not published by this repository.
Redis (`6379`), Qdrant (`6333`, `6334`), and Flower (`5555`) are bound to
`127.0.0.1` in `docker-compose.yml` so they are not published on every
interface. Containers still reach Redis and Qdrant on the Docker network.

## 1. Dedicated non-root user

`services/Dockerfile` creates `trackflow` (uid `10001`) and ends with
`USER trackflow`. The image no longer starts uvicorn with `--reload`.

On the server, application processes and deploys should use that user, not
root:

```bash
sudo useradd --create-home --uid 10001 --shell /usr/sbin/nologin trackflow
```

Skip the `useradd` line if the account already exists.

## 2. Direct SSH root login

On the server, `/etc/ssh/sshd_config` must contain:

```
PermitRootLogin no
```

Reload sshd only after a second session can still log in as the operations
user. This repository cannot change the host sshd.

## 3. Folder permissions

Apply on the server, replacing `/opt/trackflow` with the real install path:

```bash
sudo chown -R trackflow:trackflow /opt/trackflow
sudo chmod 755 /opt/trackflow
sudo chmod 750 /opt/trackflow/logs
sudo chmod 700 /opt/trackflow/secrets
sudo chmod 600 /opt/trackflow/secrets/*
```

- Application code: owner `trackflow`, directories `755`, files `644`.
- Logs: `750` so only the service user and the operations group can read them.
- Secrets and `.env`: directory `700`, files `600`. Do not commit those files.

## 4. Firewall

Expose the public application ports and SSH for operations. Do not expose
Redis, Qdrant, Flower, or the MCP listener (`127.0.0.1:8800` in
`.env.example`).

Example UFW policy for an operator to apply on the server:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 3000/tcp
sudo ufw allow 3001/tcp
sudo ufw allow 8000/tcp
sudo ufw enable
```

If TLS terminates on 443 in front of the apps, allow `443/tcp` and stop
publishing `3000`, `3001`, and `8000` on the public interface.

## 5. Deployment verification

Run these on the server. Do not paste secrets. This audit did not run them.

```bash
sshd -T | grep permitrootlogin
ss -tulpn
ufw status
nft list ruleset
stat /opt/trackflow /opt/trackflow/logs /opt/trackflow/secrets
nmap -Pn <host>
```

Expected intent, not observed output:

- `permitrootlogin` is `no`
- listeners on public interfaces are `22`, the public app ports, and `443` if used
- `6379`, `6333`, `6334`, and `5555` are absent from public interfaces

Repository-only check (safe to run in CI, does not touch a server):

```bash
uv run --python 3.14 --with-requirements services/requirements.txt pytest -q tests/security/test_hardening_config.py
```

## TLS

Customer-facing website and backoffice traffic must use HTTPS in production.
The compose file publishes plain HTTP for local development. Terminate TLS
at the reverse proxy. Do not put carrier credentials, JWT signing keys, or
database URLs in the image or in git.
