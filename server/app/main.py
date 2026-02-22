from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import create_db_and_tables
from .routes import habits, completions, friends, auth, debug

app = FastAPI(title="HabitFlow API", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(habits.router)
app.include_router(completions.router)
app.include_router(auth.router)
app.include_router(friends.router)
app.include_router(debug.router)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/health")
def health():
    return {"status": "healthy"}