from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from amex_core.settings import settings


def _load_json(path: Path) -> Any:
    """Load JSON from disk. Returns dict/list/None depending on file contents."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _as_list_of_dicts(value: Any, wrapper_key: str) -> list[dict[str, Any]]:
    """
    Accepts either:
      - list[dict]
      - dict like {"cards":[...]} / {"offers":[...]} / {"customers":[...]}
    Returns a safe list[dict].
    """
    if isinstance(value, dict):
        value = value.get(wrapper_key, [])
    if not isinstance(value, list):
        return []

    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            out.append(item)
    return out


@dataclass(frozen=True)
class MockStore:
    cards: list[dict[str, Any]]
    offers: list[dict[str, Any]]
    customers: list[dict[str, Any]]
    faq: list[dict[str, Any]]

    @classmethod
    def load(cls) -> "MockStore":
        base = Path(settings.AMEX_DATA_DIR)

        cards_blob = _load_json(base / "amex_cards.json")
        offers_blob = _load_json(base / "offers.json")
        customers_blob = _load_json(base / "customers_profile.json")
        faq_blob = _load_json(base / "faq.json")

        cards = _as_list_of_dicts(cards_blob, "cards")
        offers = _as_list_of_dicts(offers_blob, "offers")
        customers = _as_list_of_dicts(customers_blob, "customers")
        faq = _as_list_of_dicts(faq_blob, "faq")

        return cls(cards=cards, offers=offers, customers=customers, faq=faq)

    # ---- tool operations ----
    def search_cards(self, query: str) -> list[dict[str, Any]]:
        """
        Search across fields that actually exist in amex_cards.json:
        - id, name, type, category, benefits, rewards keys
        """
        q = (query or "").strip().lower()
        if not q:
            return self.cards

        out: list[dict[str, Any]] = []
        for c in self.cards:
            rewards_keys = " ".join(map(str, (c.get("rewards") or {}).keys()))
            benefits = " ".join(map(str, c.get("benefits", []) or []))

            hay = " ".join(
                [
                    str(c.get("id", "")),
                    str(c.get("name", "")),
                    str(c.get("type", "")),
                    str(c.get("category", "")),
                    rewards_keys,
                    benefits,
                ]
            ).lower()

            if q in hay:
                out.append(c)

        return out

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        for c in self.customers:
            if c.get("customer_id") == customer_id:
                return c
        return None

    def check_eligibility(self, customer_id: str, card_id: str) -> dict[str, Any]:
        customer = self.get_customer(customer_id)
        if not customer:
            return {"eligible": False, "reason": "Customer not found"}

        score = int(customer.get("credit_score", 0))
        income = int(customer.get("income_inr", 0))

        # Simple mock rules
        if card_id == "platinum":
            if score >= 750 and income >= 1200000:
                return {"eligible": True, "reason": "Meets Platinum mock criteria"}
            return {"eligible": False, "reason": "Needs credit_score>=750 and income_inr>=1200000"}

        if card_id == "gold":
            if score >= 700 and income >= 600000:
                return {"eligible": True, "reason": "Meets Gold mock criteria"}
            return {"eligible": False, "reason": "Needs credit_score>=700 and income_inr>=600000"}

        return {"eligible": False, "reason": "Unknown card_id"}

    def rewards_estimate(self, monthly_spend_inr: int, card_id: str) -> dict[str, Any]:
        spend = max(int(monthly_spend_inr), 0)

        # Super simplified estimate
        if card_id == "platinum":
            points = int(spend * 1.2)
        elif card_id == "gold":
            points = int(spend * 1.0)
        else:
            points = int(spend * 0.6)

        return {"monthly_spend_inr": spend, "card_id": card_id, "estimated_points": points}

    def compare_cards(self, card_ids: list[str]) -> list[dict[str, Any]]:
        wanted = {c.strip().lower() for c in (card_ids or [])}
        return [c for c in self.cards if (c.get("id") or "").lower() in wanted]
