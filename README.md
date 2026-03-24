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

### Notes from Ronnie Yalung for configuration and subsequent code updates:
- Create a venv in root, then pip install requirements.txt from root and run app (python(3) app/run.py OR uvicorn app.main:app --reload --port 8000). This puts your local .db in the root folder for ease of access and viewing, and uses the correct, and updated functions.
- Some /server functions are outdated: /app and /server/app are mismatched. Use /app and update /app for all relevant changes pertaining to the application
    - /server is obsolete for the application itself (besides maybe /tests), as /routes and /services are in the root /app.

FURTHER NOTE: Take this information with a grain of salt. I may be wrong, but these statements and fixes/changes helped me wrap my head around the codebase.

Health check:

- `GET http://127.0.0.1:8000/health`

