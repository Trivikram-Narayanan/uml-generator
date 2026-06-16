# Contributing

## Setup

```bash
# Backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.ingest
cp .env.example .env
# Set LLM_BACKEND=mock in .env for local dev without a model
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend
npm install
REACT_APP_API_URL=http://localhost:8000 npm start
```

## Project layout

```
backend/
  api/routers/    one file per feature area
  llm/            all LLM backends — only local_llm.py calls models
  rag/            ChromaDB retriever + prompt builder
  db/             SQLAlchemy models + session
  auth/           JWT + bcrypt (optional, off by default)
  scripts/        ingest.py builds the knowledge base
  tests/          pytest suite

frontend/src/
  pages/AppPage.js     main workspace
  components/          DiagramPreview, CodePanel, VersionHistory, …
  hooks/useGenerate.js all API calls
  utils/api.js         fetch wrapper
```

## Adding a new LLM backend

Edit `backend/llm/local_llm.py`. Add your function and register it in the `dispatch` dict:

```python
def _my_backend(prompt: str) -> str:
    # call your model
    return raw_text

dispatch = { ..., "my_backend": _my_backend }
```

Set `LLM_BACKEND=my_backend` in `.env`.

## Adding UML examples to the knowledge base

Edit `CANONICAL_EXAMPLES` or `UML_RULES` in `backend/scripts/ingest.py`, then rebuild:

```bash
python -m scripts.ingest
```

## Tests

```bash
cd backend
pytest                    # runs all tests
pytest tests/test_auth.py # specific file
```

Tests use an in-memory SQLite DB and `LLM_BACKEND=mock` — nothing external needed.

## Submitting a pull request

- Keep PRs focused — one thing at a time
- `pytest` should pass with no new failures
- `npm run build` should succeed
- New API routes need a test in `tests/`
- No `.env` files or secrets committed

Open an issue before starting work on anything big — saves everyone time if the direction doesn't fit.
