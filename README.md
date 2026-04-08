# FollowThru

Habit-building app with an iOS client and a FastAPI backend.

## Repository layout

```
FollowThru/
├── app/                  # FastAPI backend
│   ├── routes/           # API route handlers
│   ├── services/         # Business logic and AI pipeline
│   ├── models.py         # Pydantic + SQLModel data models
│   ├── main.py           # App entry point
│   └── config.py         # Environment config
├── tests/                # Backend test suite
├── ios/FollowThru/       # iOS Xcode project
├── requirements.txt
└── pytest.ini
```

## Running the backend

From the repo root:

```bash
python -m uvicorn app.main:app --reload
```

The server starts at `http://127.0.0.1:8000`.

Health check: `GET http://127.0.0.1:8000/health`

### Environment setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your `OPENAI_API_KEY`.

## Running the iOS app

1. Open `ios/FollowThru/FollowThru.xcodeproj` in Xcode
2. Select the `FollowThru` scheme
3. Choose an iPhone simulator
4. Build and run (`Cmd+R`)

The simulator connects to `http://127.0.0.1:8000` by default. To run on a physical device, set `API_BASE_URL` in the Xcode scheme environment variables to your Mac's local IP (e.g. `http://192.168.1.10:8000`).

## Running the tests

```bash
source .venv/bin/activate
pytest
```

Test files are in `tests/`. `test_chat_unit.py` covers the AI chat pipeline with no network or database required.
