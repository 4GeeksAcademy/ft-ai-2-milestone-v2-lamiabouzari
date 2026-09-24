# Testing

## Commands

This repository currently declares Python dependencies in `services/requirements.txt` and has no `pyproject.toml` or `uv.lock`. The project virtual environment is under `services/.venv`.

```bash
export JWT_SECRET=test-only-validation-secret
services/.venv/bin/pytest -q
services/.venv/bin/pytest -q --cov=routers.auth --cov-report=term-missing
```

The exact assignment commands were also checked. Both `uv run pytest` and `uv run pytest --cov` fail with shell status 127 because `uv` is not installed. There is also no `pyproject.toml` or `uv.lock`; adding a project-management migration solely for these aliases would be disproportionate. `pytest` and `pytest-cov` are declared as test dependencies in `services/requirements.txt`; install them with the existing requirements if creating a fresh environment.

The complete suite must be run from the repository root. Authentication tests use an in-memory TinyDB fixture and patch `database.get_db`, `routers.auth.get_db`, and `dependencies.get_db`, so they never read or write the real application database. Reset-email delivery is mocked in tests.

## Authentication test plan

| Concern | Happy path | Edge case | Failure mode |
| --- | --- | --- | --- |
| Register | Creates a user and linked profile; default role is `user`. | Optional profile fields are persisted and password is never stored as plaintext. | Duplicate email returns the application conflict error; short and overlong passwords are rejected. |
| Login | Correct credentials return a bearer JWT whose `sub` is the persisted user ID. | Inactive users are explicitly checked. | Wrong password, unknown email, and inactive users return the same invalid-credentials error. |
| Profile update | Authenticated owner updates `PUT /profiles/me`; user data remains unchanged. | Empty optional phone is accepted and persisted by the existing schema. | Missing authentication returns 401. |
| Access token/current user | Valid JWT resolves the correct public user. | `/auth/me` returns the linked profile and missing profiles return the expected 404. | Malformed, expired, subject-less, and nonexistent-user tokens are rejected. |
| Forgot/request reset | Existing email creates a reset token and delegates/sends the reset operation. | Both reset endpoints use the same generic response for unknown email, preventing enumeration. | Email delivery is simulated/mocked; no network email is sent. |
| Reset password | Valid reset token changes the password and stores a hash. | Reset token becomes stale after the password changes. | Malformed, expired, wrong-purpose, missing-user, and reused tokens are rejected. |
| Change password | Correct current password changes the password and stores a hash. | New password is verified against the new hash. | Incorrect current password and missing user are rejected. |
| Helpers | Access/reset JWT helpers, Gravatar generation, reset-link construction, and reset-token decoding are exercised. | Reset token includes the password-reset purpose and issued-at timestamp. | Invalid reset JWT claims are rejected. |

## Results

Latest complete run:

```text
38 passed, 0 failed, 2 warnings
```

Authentication coverage (`services/routers/auth.py`): **83%** (167 statements, 29 missed), using:

```bash
services/.venv/bin/pytest -q --cov=routers.auth --cov-report=term-missing
```

The warnings are existing dependency/deprecation warnings from FastAPI/Starlette and the application's deprecated HTTP 422 constant; they do not fail the suite.

## AI-assisted review note

AI assistance identified the security-sensitive cases that are easy to miss in a basic happy-path suite: generic reset responses for unknown emails, reset-token purpose validation, password-change invalidation via `password_changed_at`, and ensuring persisted passwords are hashes. These cases are covered in `tests/test_password.py` and `tests/test_token.py`.

The tests found a genuine authentication defect: `POST /auth/login` accepted valid credentials for users whose `is_active` flag was false. The smallest fix adds an inactive-user check and raises the existing generic `invalid_credentials()` exception, avoiding account-status enumeration. Profile tests were also added in `tests/test_profiles.py`. The tests retain the application's distinction between Pydantic short-password validation and its custom `PASSWORD_TOO_LONG` exception.
