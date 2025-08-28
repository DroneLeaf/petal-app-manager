"""
Admin UI API router
Provides a web-based dashboard for managing the Petal App Manager system.
"""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from typing import Optional

router = APIRouter(prefix="/admin", tags=["Admin UI"])

# Initialize Jinja2 templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

_logger: Optional[logging.Logger] = None

def _set_logger(logger: logging.Logger):
    """Set the logger for api endpoints."""
    global _logger
    _logger = logger

def get_logger() -> logging.Logger:
    """Get the logger instance."""
    global _logger
    if not _logger:
        _logger = logging.getLogger("PetalAppManagerAPI")
    return _logger

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard with real-time log streaming"""
    return templates.TemplateResponse("admin-dashboard.html", {"request": request})
