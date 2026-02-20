# FollowThru

Habit-building app with an iOS client and a FastAPI backend.

## Repository layout

- `ios/FollowThru`: iOS app project
- `server`: FastAPI backend

## iOS quick start

1. Open `ios/FollowThru/FollowThru.xcodeproj` in Xcode.
2. Select scheme `FollowThru`.
3. Select a simulator (for example, iPhone).
4. Build with `Cmd+B`.
5. Run with `Cmd+R`.

## Backend quick start

1. `cd server`
2. `python3 -m venv .venv`
3. `source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. `uvicorn app.main:app --reload --port 8000`

Health check:

- `GET http://127.0.0.1:8000/health`

