# FollowThru

Habit-building app with an iOS client and a FastAPI backend.

## Repository layout

- `ios/FollowThru`: iOS app project
- `app`: FastAPI backend

## Run the app

### 1. Start the backend

1. Copy `.env.example` to `.env` at the repo root:

   ```bash
   cp .env.example .env
   ```

2. Set your real OpenAI key in `.env`:

   ```env
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o-mini
   ```

3. From the repo root, run:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python3 app/run.py
   ```

   Or with uvicorn directly:

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

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
- If you run the app on a physical device instead of a simulator, set `API_BASE_URL` in the Xcode scheme environment to your Mac's LAN IP, for example `http://192.168.1.10:8000`.

## Backend tests

```bash
source .venv/bin/activate
pytest
```
