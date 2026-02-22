import os
import sys
import uvicorn

if __name__ == "__main__":
    # Enable debug endpoints
    os.environ["ENABLE_DEBUG_ENDPOINTS"] = "1"

    # Add .../server to Python path so `import app` works
    HERE = os.path.dirname(__file__)              # .../server/app
    SERVER_DIR = os.path.abspath(os.path.join(HERE, ".."))  # .../server
    sys.path.insert(0, SERVER_DIR)

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )