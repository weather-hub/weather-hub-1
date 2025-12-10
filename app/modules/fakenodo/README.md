# Fakenodo

This module provides a lightweight local emulation of a Zenodo-like API for development and testing.

## Purpose

- Emulate basic Zenodo behaviour (create deposition, upload files, publish versions) without calling external services.
- Allow uvlhub/weather-hub development and CI to run without network dependency on Zenodo.
- Enable testing of the Zenodo integration flow without relying on external APIs.

## Configuration

Fakenodo is used instead of the real Zenodo API when:

### Option 1: Explicit Configuration (Recommended)
```bash
export USE_FAKE_ZENODO=true
# Then run the app
```

### Option 2: Using External Fakenodo Service (Advanced)
```bash
export FAKENODO_URL=http://localhost:5000
```

### Option 3: Default Behavior (No Environment Variables)
- Tries to connect to the real Zenodo API
- Falls back to Fakenodo if connection fails (network issues, SSL problems, etc.)

## Core Logic

### Zenodo Behavior Emulation

**Edit metadata only → NO new DOI:**
```python
# Updating metadata alone does NOT mark the deposition as dirty
update_metadata(deposition_id, new_metadata)
publish_deposition(deposition_id)
# Returns the same DOI as before (no new version)
```

**Add/change files and publish → generates new DOI/version:**
```python
# Uploading a file marks the deposition as dirty
upload_file(deposition_id, filename, content)
publish_deposition(deposition_id)
# Returns a NEW DOI with incremented version (e.g., v1 → v2)
```

## API Endpoints

### Depositions
- **POST** `/deposit/depositions` — Create a deposition
  ```json
  {"metadata": {"title": "My Dataset"}}
  ```

- **GET** `/deposit/depositions` — List all depositions

- **GET** `/deposit/depositions/<id>` — Get a specific deposition

- **PUT** `/deposit/depositions/<id>` — Update metadata (does NOT mark dirty)
  ```json
  {"metadata": {"title": "Updated Title"}}
  ```

- **DELETE** `/deposit/depositions/<id>` — Delete a deposition

### Files
- **POST** `/deposit/depositions/<id>/files` — Upload a file (marks dirty)
  - Form parameter: `file` (multipart file upload)

### Publishing & Versions
- **POST** `/deposit/depositions/<id>/actions/publish` — Publish deposition and create/update version

- **GET** `/deposit/depositions/<id>/versions` — List all versions for a deposition

## Response Format

All responses include Zenodo-compatible fields:
```json
{
  "id": 1,
  "conceptrecid": 1,
  "state": "draft|published",
  "metadata": {...},
  "files": [...],
  "versions": [...],
  "links": {
    "self": "/api/deposit/depositions/1",
    "publish": "/api/deposit/depositions/1/actions/publish"
  },
  "created_at": "2025-12-07T...",
  "updated_at": "2025-12-07T..."
}
```

## DOI Generation

When a deposition is published, a fake DOI is generated in the format:
```
10.1234/fakenodo.{dataset_id}.v{version}
```

Example:
- First publication: `10.1234/fakenodo.1.v1`
- Second publication (after file change): `10.1234/fakenodo.1.v2`

**Important in Production (Render, Heroku, etc.):**
- The DOI uses `dataset_id` (from database) instead of `deposition_id` (from JSON)
- This ensures stable, unique DOIs even when the JSON database is reset between deployments

## Persistence

### Local Development
- Data is persisted to `fakenodo_db.json` in `WORKING_DIR` (or current directory if not set)
- File is added to `.gitignore` — do not commit it

### Production (Render, Heroku, etc.)
- `fakenodo_db.json` is ephemeral (files are lost on deployment)
- DOIs remain stable because they're based on `dataset_id` from the persistent SQL database
- If you need permanent Fakenodo storage, consider migrating to SQL backend

## Cleaning Between Runs

In CI or when running tests in parallel:
```bash
# Set WORKING_DIR to a unique temporary folder per job
export WORKING_DIR=/tmp/fakenodo_test_$$
# Run tests
# Clean up after
rm -rf /tmp/fakenodo_test_$$
```

## Thread Safety

- All operations are protected with `threading.Lock()`
- Safe for concurrent requests
- Safe for multi-threaded environments

## Error Handling

All error responses use consistent format:
```json
{"message": "Error description"}
```

HTTP Status Codes:
- `201` - Resource created
- `200` - Success
- `202` - Accepted (for async operations like publish)
- `400` - Bad request (missing parameters)
- `404` - Resource not found

## Testing

### Unit Tests
See `app/modules/fakenodo/tests/test_flow.py` for logic tests demonstrating:
- Metadata edit without DOI change
- File upload with DOI change
- Adapter pattern compatibility

### E2E Test Endpoint
```bash
curl http://localhost:5000/fakenodo/test
```

This endpoint runs a complete flow:
1. Create deposition
2. Upload file
3. Publish
4. Delete

## Security

⚠️ **This is a development-only service. DO NOT expose it in production.**

If you need Fakenodo in production:
- Use it only in development environments
- Never expose port/endpoints to public internet
- Consider using real Zenodo for production

## Integration with Weather-Hub/UVLHub

### FakenodoAdapter
The `FakenodoAdapter` class in `dataset/routes.py` provides a Zenodo-compatible interface:
```python
adapter = FakenodoAdapter()
deposition = adapter.create_new_deposition(dataset)
adapter.upload_file(dataset, deposition_id, feature_model)
version = adapter.publish_deposition(deposition_id)
doi = adapter.get_doi(deposition_id)
```

The adapter ensures:
- Stable DOI generation using `dataset.id`
- Zenodo API compatibility
- Fallback behavior if Zenodo fails
