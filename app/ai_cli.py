from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import uuid


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Test the AI habit pipeline routes in-process.")
    p.add_argument("--goal", required=True, help="Natural-language habit goal")
    p.add_argument("--category", required=True, choices=["fitness", "study", "wellness", "reading", "sleep"])
    p.add_argument("--experience-level", default="beginner")
    p.add_argument("--available-time", type=int, default=15, help="Minutes available")
    p.add_argument("--preferred-time", default="flexible", choices=["morning", "afternoon", "evening", "flexible"])
    p.add_argument("--create", action="store_true", help="Call /api/ai/generate-and-create instead of generate-plan")
    p.add_argument("--mock", action="store_true", help="Use mock AI provider (no OpenAI call)")
    p.add_argument("--db-url", default="", help="Override DATABASE_URL for the test run")
    p.add_argument("--keep-raw", action="store_true", help="Include raw_plan in printed output")
    return p.parse_args()


def _configure_env(args: argparse.Namespace) -> None:
    if args.mock:
        os.environ["AI_PROVIDER"] = "mock"
    if args.db_url:
        os.environ["DATABASE_URL"] = args.db_url
    else:
        # Use a temp sqlite DB by default so the script doesn't mutate repo-local DB files.
        os.environ.setdefault("DATABASE_URL", f"sqlite:////tmp/followthru_ai_cli_{uuid.uuid4().hex}.db")
    os.environ.setdefault("SECRET_KEY", "ai-cli-dev-secret")


def _import_app():
    # Ensure the repo root is on sys.path so `from app.main import app` works
    # regardless of cwd (repo root, app/, etc.).
    here = Path(__file__).resolve()  # .../app/ai_cli.py
    repo_root = here.parent.parent   # .../FollowThru

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from app.main import app  # type: ignore
    return app


def _register_and_login(client):
    email = f"ai-cli-{uuid.uuid4().hex[:8]}@example.com"
    password = "Password123!"
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": "AI CLI User"},
    )
    if reg.status_code != 201:
        raise RuntimeError(f"Register failed: {reg.status_code} {reg.text}")
    token = reg.json()["access_token"]
    return token


def main() -> int:
    args = parse_args()
    _configure_env(args)

    try:
        from fastapi.testclient import TestClient
    except RuntimeError as exc:
        if "httpx" in str(exc).lower():
            print("Missing dependency: httpx", file=sys.stderr)
            print("Install with: pip install httpx  (or pip install -r requirements.txt)", file=sys.stderr)
            return 2
        raise

    app = _import_app()

    endpoint = "/api/ai/generate-and-create" if args.create else "/api/ai/generate-plan"
    body = {
        "user_goal": args.goal,
        "category": args.category,
        "context": {
            "experience_level": args.experience_level,
            "available_time": args.available_time,
            "preferred_time": args.preferred_time,
        },
    }

    with TestClient(app) as client:
        token = _register_and_login(client)
        resp = client.post(
            endpoint,
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )

    if resp.status_code not in (200, 201):
        print(f"Request failed: {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        return 1

    data = resp.json()
    if not args.keep_raw:
        data.pop("raw_plan", None)
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
