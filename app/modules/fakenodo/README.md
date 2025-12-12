# Fakenodo

This module provides a lightweight local emulation of a Zenodo-like API for development and testing.

Purpose
- Emulate basic Zenodo behaviour (create deposition, upload files, publish versions) without calling external services.
- Allow uvlhub development and CI to run without network dependency on Zenodo.

Usage
- By default the application uses the real `ZenodoService` for production flows. To prefer the fake service set one of the environment variables:
  - `FAKENODO_URL` (any value) or
  - `USE_FAKE_ZENODO=true`

  Example (bash):

  ```bash
  export USE_FAKE_ZENODO=true
  # then run the app
  ```

Behaviour notes
- Endpoints implemented:
  - POST `/fakenodo/deposit/depositions` — create a deposition (accepts JSON with `metadata`).
  - GET `/fakenodo/deposit/depositions` — list depositions.
  - GET `/fakenodo/deposit/depositions/<id>` — get a deposition.
  - PUT `/fakenodo/deposit/depositions/<id>` — update only metadata (will NOT mark the deposition as dirty).
  - DELETE `/fakenodo/deposit/depositions/<id>` — delete a deposition.
  - POST `/fakenodo/deposit/depositions/<id>/files` — upload a file (multipart form `file`). Marks the deposition as dirty.
  - POST `/fakenodo/deposit/depositions/<id>/actions/publish` — publish deposition; creates a new DOI/version if there is no previous version or if the deposition is dirty.
  - GET `/fakenodo/deposit/depositions/<id>/versions` — list versions for a deposition.

- DOI generation: a fake DOI of the form `10.1234/fakenodo.{id}.v{version}` is returned on publish.

Persistence & cleanup
- Data is persisted to `fakenodo_db.json` in `WORKING_DIR` (or current working dir if `WORKING_DIR` not set).
- Files uploaded are recorded in the DB metadata but their bytes are not stored on disk by default.
- `fakenodo_db.json` is added to `.gitignore` — do not commit it.

Cleaning between runs
- In CI or when running tests in parallel, set `WORKING_DIR` to a unique temporary folder per job and remove that folder after the run.

Security
- This is a development-only service. Do NOT expose it in production.

Testing
- Unit tests live in `app/modules/fakenodo/tests` and demonstrate the create/edit/publish behaviour.

If you want behaviour changes (e.g. persist file bytes, different DOI format, additional endpoints) open a PR with the desired behaviour and tests.
