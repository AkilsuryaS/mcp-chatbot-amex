from __future__ import annotations

from fastapi import APIRouter
from amex_core.services import MockStore

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/cards")
def cards() -> list[dict]:
    return MockStore.load().cards


@router.get("/offers")
def offers() -> list[dict]:
    return MockStore.load().offers


@router.get("/customers")
def customers() -> list[dict]:
    return MockStore.load().customers
