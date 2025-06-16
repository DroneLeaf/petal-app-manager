from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}