"""Health routes module."""
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
