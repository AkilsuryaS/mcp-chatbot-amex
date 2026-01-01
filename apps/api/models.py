from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: str = Field(default="default", description="Client-provided session id")
    customer_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    tools_used: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


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
