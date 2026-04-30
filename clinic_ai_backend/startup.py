"""Startup entrypoint module."""
import uvicorn

from src.app import app
from src.core.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
