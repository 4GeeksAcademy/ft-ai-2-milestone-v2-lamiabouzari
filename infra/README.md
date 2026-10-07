# `infra` folder

This folder contains **infrastructure configurations** for the monorepo (for example: Dockerfiles, Terraform scripts, deployment manifests, Nginx configs, etc.).

- **Main purpose**: to centralize the definition of the infrastructure required to run the company's applications and services.
- **Recommendation**: document how to provision and deploy the infrastructure.
- Host hardening for operators is `server-hardening.sh` plus `docs/security/server-hardening.md`. The script refuses to run unless `TRACKFLOW_CONFIRM_SERVER_HARDENING=yes` on the target machine.

> _Spanish version: [README.es.md](./README.es.md)._
