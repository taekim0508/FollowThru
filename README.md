# FollowThru

Habit-building app with an iOS client and a FastAPI backend.

## Repository layout

- `ios/FollowThru`: iOS app project
- `server`: FastAPI backend

## Run the app

### 1. Start the backend

1. Open `server/.env`
2. Set your real OpenAI key:

   ```env
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o-mini
   ```

3. From the repo root, run:

   ```bash
   ./run_backend_ai.sh
   ```

What the script does:

- creates `.venv` if it does not exist
- installs backend dependencies if they are missing
- creates `server/.env` from `server/.env.example` if needed
- forces `AI_PROVIDER=openai`
- starts the FastAPI backend on `http://127.0.0.1:8000`

### Notes from Ronnie Yalung for configuration and subsequent code updates:
- Create a venv in root, then pip install requirements.txt from root and run app (python(3) app/run.py OR uvicorn app.main:app --reload --port 8000). This puts your local .db in the root folder for ease of access and viewing, and uses the correct, and updated functions.
- Some /server functions are outdated: /app and /server/app are mismatched. Use /app and update /app for all relevant changes pertaining to the application
    - /server is obsolete for the application itself (besides maybe /tests), as /routes and /services are in the root /app.

FURTHER NOTE: Take this information with a grain of salt. I may be wrong, but these statements and fixes/changes helped me wrap my head around the codebase.

Health check:

- `GET http://127.0.0.1:8000/health`

### 2. Run the iOS frontend

1. Open `ios/FollowThru/FollowThru.xcodeproj` in Xcode
2. Select scheme `FollowThru`
3. Choose an iPhone simulator
4. Build with `Cmd+B`
5. Run with `Cmd+R`

### Backend/frontend connection

- The iOS simulator uses `http://127.0.0.1:8000` by default for the backend.
- `./run_backend_ai.sh` starts the backend on that same address, so the simulator frontend should connect without extra setup.
- If you run the app on a physical device instead of a simulator, set `API_BASE_URL` in the Xcode scheme environment to your Mac's LAN IP, for example `http://192.168.1.10:8000`.

## Backend tests

```bash
source .venv/bin/activate
python3 -m pip install pytest
python3 -m pytest server/tests/test_auth.py server/tests/test_habits.py server/tests/test_ai.py
```
