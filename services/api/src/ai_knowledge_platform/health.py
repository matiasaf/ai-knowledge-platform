"""Liveness endpoint."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from ai_knowledge_platform import __version__

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health", summary="Liveness probe")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
