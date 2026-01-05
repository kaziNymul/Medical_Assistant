"""
Main entry point for the Medical Assistant.

Run with:
    python -m src.main
    
Or:
    uvicorn src.api.app:app --reload
"""

import uvicorn

from config.settings import settings


def main():
    """Run the FastAPI application."""
    uvicorn.run(
        "src.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
