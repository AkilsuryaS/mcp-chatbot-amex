from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from amex_core.services import MockStore

mcp = FastMCP("amex-mock-mcp")


# -------------------------
# Health check (root)
# -------------------------
@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


# -------------------------
# Tools
# -------------------------
@mcp.tool
def list_cards() -> list[dict[str, Any]]:
    store = MockStore.load()
    cards = getattr(store, "cards", []) or []
    if isinstance(cards, dict):
        cards = cards.get("cards", [])
    return cards if isinstance(cards, list) else []


@mcp.tool
def list_offers() -> list[dict[str, Any]]:
    store = MockStore.load()
    offers = getattr(store, "offers", None)

    if isinstance(offers, dict):
        flat: list[dict[str, Any]] = []
        for v in offers.values():
            if isinstance(v, list):
                flat.extend(v)
        return flat

    return offers or []


@mcp.tool
def search_faq(question: str) -> list[dict[str, Any]]:
    store = MockStore.load()
    faqs: list[dict[str, Any]] = getattr(store, "faq", []) or []

    q = (question or "").strip().lower()
    if not q:
        return []

    q_terms = [t for t in q.replace("?", " ").replace(",", " ").split() if t]
    scored: list[tuple[int, dict[str, Any]]] = []

    for item in faqs:
        text = f"{item.get('question','')} {item.get('answer','')}".lower()
        score = sum(1 for t in q_terms if t in text)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:5]]


@mcp.tool
def search_cards(query: str) -> list[dict[str, Any]]:
    store = MockStore.load()
    return store.search_cards(query)


@mcp.tool
def check_eligibility(customer_id: str, card_id: str) -> dict[str, Any]:
    store = MockStore.load()
    return store.check_eligibility(customer_id, card_id)


@mcp.tool
def compare_cards(card_ids: list[str]) -> list[dict[str, Any]]:
    store = MockStore.load()
    return store.compare_cards(card_ids)


@mcp.tool
def rewards_estimate(monthly_spend_inr: int, card_id: str) -> dict[str, Any]:
    store = MockStore.load()
    return store.rewards_estimate(monthly_spend_inr, card_id)


if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8765"))

    # IMPORTANT: run MCP at ROOT for StreamableHttpTransport
    mcp.run(transport="http", host=host, port=port)
