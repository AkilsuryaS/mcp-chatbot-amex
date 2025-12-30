from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP

from amex_core.services import MockStore

from starlette.requests import Request
from starlette.responses import PlainTextResponse

mcp = FastMCP("amex-mock-mcp")

# mcp health check
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")



# -------------------------
# New tools
# -------------------------

@mcp.tool
def list_cards() -> list[dict[str, Any]]:
    """
    Return all cards from mock data as a flat list.
    """
    store = MockStore.load()

    cards = getattr(store, "cards", []) or []

    # If cards accidentally comes wrapped like {"cards":[...]}
    if isinstance(cards, dict):
        cards = cards.get("cards", [])

    # Defensive: ensure list
    if not isinstance(cards, list):
        return []

    return cards


@mcp.tool
def list_offers() -> list[dict[str, Any]]:
    """
    Return all offers as a flat list.
    """
    store = MockStore.load()
    offers = getattr(store, "offers", None)

    # If your mock data groups offers in a dict, flatten it.
    if isinstance(offers, dict):
        flat: list[dict[str, Any]] = []
        for v in offers.values():
            if isinstance(v, list):
                flat.extend(v)
        return flat

    # If it's already a list, return it.
    return offers or []



@mcp.tool
def search_faq(question: str) -> list[dict[str, Any]]:
    """
    Search FAQs using a simple keyword match and return best candidates.
    (LLM will do the reasoning; this just returns plausible matches.)
    """
    store = MockStore.load()
    faqs: list[dict[str, Any]] = getattr(store, "faq", []) or []

    q = (question or "").strip().lower()
    if not q:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    q_terms = [t for t in q.replace("?", " ").replace(",", " ").split() if t]

    for item in faqs:
        text = f"{item.get('question','')} {item.get('answer','')}".lower()
        score = sum(1 for t in q_terms if t in text)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:5]]


# -------------------------
# Existing tools (keep yours)
# -------------------------
# If you already have these in your current server.py, keep them.
# If not, you can implement or remove these based on your zip parity.

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
    # Streamable HTTP is the recommended production transport. :contentReference[oaicite:1]{index=1}
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8765"))
    path = os.getenv("MCP_PATH", "/mcp")

    mcp.run(transport="http", host=host, port=port, path=path)
