from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from amex_core.settings import settings


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class MockStore:
    cards: list[dict[str, Any]]
    offers: list[dict[str, Any]]
    customers: list[dict[str, Any]]

    @classmethod
    def load(cls) -> "MockStore":
        base = Path(settings.AMEX_DATA_DIR)
        return cls(
            cards=_load_json(base / "cards.json"),
            offers=_load_json(base / "offers.json"),
            customers=_load_json(base / "customers.json"),
        )

    # ---- simple “tool” operations ----
    def search_cards(self, query: str) -> list[dict[str, Any]]:
        q = (query or "").strip().lower()
        if not q:
            return self.cards
        out: list[dict[str, Any]] = []
        for c in self.cards:
            hay = " ".join(
                [
                    str(c.get("id", "")),
                    str(c.get("name", "")),
                    str(c.get("reward_rate", "")),
                    " ".join(c.get("best_for", []) or []),
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
        wanted = set(card_ids)
        return [c for c in self.cards if c.get("id") in wanted]
