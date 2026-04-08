import os
import sys
import uvicorn

if __name__ == "__main__":
    # Enable debug endpoints
    os.environ["ENABLE_DEBUG_ENDPOINTS"] = "1"

    # Add repo root to Python path so `import app` works
    HERE = os.path.dirname(__file__)              # .../app
    REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))  # repo root
    sys.path.insert(0, REPO_ROOT)

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )