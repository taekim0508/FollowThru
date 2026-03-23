# HabitFlow Server

FastAPI backend for HabitFlow.

## Start the backend in AI mode

From the repo root:

```bash
./run_backend_ai.sh
```

The script will:

- create the repo-root `.venv` if needed
- install backend dependencies if they are missing
- load `server/.env`
- force `AI_PROVIDER=openai`
- start `uvicorn` on `http://127.0.0.1:8000`

Before running it, make sure `server/.env` contains a real `OPENAI_API_KEY`.

## AI local testing

The in-process CLI harness can hit the auth + AI flow end to end:

```bash
python -m app.ai_cli --mock --goal "I want to read every day" --category reading
python -m app.ai_cli --mock --create --goal "I want to work out on weekdays" --category fitness
```

To use mock mode instead of real OpenAI calls:

```bash
cd server
AI_PROVIDER=mock uvicorn app.main:app --reload
```

Targeted backend checks:

```bash
python -m pytest server/tests/test_auth.py server/tests/test_habits.py server/tests/test_ai.py
```
