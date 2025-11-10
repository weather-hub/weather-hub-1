# fakenodo

This module provides a small fake implementation of the Zenodo deposition API for local development and tests.

Run standalone:

```bash
# from repository root
python -m app.modules.fakenodo.run
```

By default it listens on port 5001. You can change port with:

```bash
FAKENODO_PORT=5002 python -m app.modules.fakenodo.run
```

Point the main app to the fake service by setting the `FAKENODO_URL` environment variable, for example:

```bash
export FAKENODO_URL=http://localhost:5001/deposit/depositions
# then start the main app normally
flask run
```

Basic sequence to exercise the fake:

```bash
# create
curl -s -X POST -H "Content-Type: application/json" -d '{"metadata": {"title":"test"}}' http://localhost:5001/deposit/depositions | jq

# upload (multipart)
curl -s -X POST -F "file=@test.csv" http://localhost:5001/deposit/depositions/1/files | jq

# publish
curl -s -X POST http://localhost:5001/deposit/depositions/1/actions/publish | jq

# get
curl -s http://localhost:5001/deposit/depositions/1 | jq
```
