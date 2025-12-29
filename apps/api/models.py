from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    customer_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    tools_used: list[str] = []
    suggestions: list[str] = []


class EligibilityRequest(BaseModel):
    customer_id: str
    card_id: str


class RewardsRequest(BaseModel):
    card_id: str
    monthly_spend_inr: int = Field(..., ge=0)


class CompareRequest(BaseModel):
    card_ids: list[str] = Field(..., min_length=1)


class SearchRequest(BaseModel):
    query: str = ""
