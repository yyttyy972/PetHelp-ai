# C1 AI adapter for B0 backend

This is a reviewable integration branch based on B0. All integration code is added as new files. Existing B0 business source, schemas, database scripts, seed data, requirements.txt, smoke tests, and standard app.main are left unchanged.

## Added
- `app/ai/`: C0 parser adapted to backend-relative Prompt/Schema paths, plus authenticated router and contract checks.
- `run_ai_integration.py`: independent local entry point replacing the existing 503 placeholder at runtime only.
- `requirements-ai.txt`: B0 requirements plus AI-only dependencies.
- `tests/test_ai_integration.py`: five offline contract tests.
- `docs/week9/ai-parse-schema.json`, `docs/week10/prompt-v2.md`: AI contract assets.

## Run (PowerShell, from backend directory)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
# Put DATABASE_URL, JWT_SECRET and AI_API_KEY in backend/.env locally; never commit .env.
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_ai_integration.py
.\.venv\Scripts\python.exe -m uvicorn run_ai_integration:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`. POST `/api/v0/ai/parse` requires Bearer authentication and `text`, timezone-aware `reference_time`, IANA `timezone`, and selected `pet_ids`. The adapter reads only the signed-in owner's selected pets. The response is a draft plus questions; it does not create or publish a ServiceRequest. B0's normal request endpoint still requires all mandatory fields to be completed.

## Review boundary

B should review and explicitly register the router in the standard app entry point and decide dependency placement before the team treats this as the production backend. This branch is not merged into B0.
