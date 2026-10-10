# `services` folder

This folder contains **all the backend services** (APIs and background workers) related to the company for the cross-functional AI Engineering project.

Each subfolder inside `services/` must correspond to **one specific service** (for example: `admin-api`, `data-processor-worker`) and include its own technical and functional documentation.

- **Main purpose**: to centralize all the backend logic, APIs, and queue consumers that support the company's use cases.
- **Recommendation**: document in this file (or in sub-READMEs) the services you add, their objective, the technology used, and how to run them.

> _Spanish version: [README.es.md](./README.es.md)._

## Supplier directory

The supplier API is not a second server. `services/api` is mounted on the FastAPI app in `services/main.py` (http://127.0.0.1:8000). Supplier rows are stored only in the TinyDB table `suppliers`.

From this directory, the seed dependencies are declared in `pyproject.toml`. The project is unmanaged (`tool.uv.managed = false`) so `uv sync` must not be run: it would replace `services/.venv`.

Install the entry point into the existing application virtualenv, then seed:

```text
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
uv run seed
```

A clean virtualenv can run it with the declared dependencies instead of `--no-deps`:

```text
uv venv <clean-venv> --python 3.12
uv pip install -e . --python <clean-venv>\Scripts\python.exe
uv run --python <clean-venv>\Scripts\python.exe seed
```
