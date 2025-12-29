from __future__ import annotations

from fastapi import APIRouter

from amex_core.services import MockStore
from apps.api.models import CompareRequest, EligibilityRequest, RewardsRequest, SearchRequest

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
def list_tools() -> list[dict]:
    return [
        {"name": "search_cards", "description": "Search cards by text query"},
        {"name": "check_eligibility", "description": "Eligibility check for a customer+card"},
        {"name": "rewards_estimate", "description": "Estimate monthly reward points"},
        {"name": "compare_cards", "description": "Compare cards by IDs"},
    ]


@router.post("/search")
def search(req: SearchRequest) -> list[dict]:
    return MockStore.load().search_cards(req.query)


@router.post("/eligibility")
def eligibility(req: EligibilityRequest) -> dict:
    return MockStore.load().check_eligibility(req.customer_id, req.card_id)


@router.post("/rewards")
def rewards(req: RewardsRequest) -> dict:
    return MockStore.load().rewards_estimate(req.monthly_spend_inr, req.card_id)


@router.post("/compare")
def compare(req: CompareRequest) -> list[dict]:
    return MockStore.load().compare_cards(req.card_ids)
