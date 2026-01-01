from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from amex_core.settings import settings


def _load_json_any(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _unwrap_list(payload: Any, key: str) -> list[dict[str, Any]]:
    """
    Accept either:
      - a list[dict]
      - or a dict like {"<key>": [ ... ]}
    Return a list[dict].
    """
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        v = payload.get(key, [])
        return v if isinstance(v, list) else []
    return []


@dataclass(frozen=True)
class MockStore:
    cards: list[dict[str, Any]]
    offers: list[dict[str, Any]]
    customers: list[dict[str, Any]]
    faq: list[dict[str, Any]]

    @classmethod
    def load(cls) -> "MockStore":
        base = Path(settings.AMEX_DATA_DIR)

        cards_raw = _load_json_any(base / "amex_cards.json")
        offers_raw = _load_json_any(base / "offers.json")
        customers_raw = _load_json_any(base / "customers_profile.json")
        faq_raw = _load_json_any(base / "faq.json")

        return cls(
            cards=_unwrap_list(cards_raw, "cards"),
            offers=_unwrap_list(offers_raw, "offers"),          # if your offers file is a list, this still works
            customers=_unwrap_list(customers_raw, "customers"),
            faq=_unwrap_list(faq_raw, "faq"),
        )

    # ---- helpers ----
    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        """
        Supports both:
          - {"id": "..."}   (your current file)
          - {"customer_id": "..."} (older style)
        """
        for c in self.customers:
            if c.get("id") == customer_id or c.get("customer_id") == customer_id:
                return c
        return None

    def _customer_credit_score(self, customer: dict[str, Any]) -> int:
        # your JSON: customer["profile"]["credit_score"]
        prof = customer.get("profile") or {}
        return int(prof.get("credit_score", 0) or 0)

    def _customer_annual_income(self, customer: dict[str, Any]) -> int:
        # your JSON: customer["profile"]["annual_income"]
        prof = customer.get("profile") or {}
        return int(prof.get("annual_income", 0) or 0)

    # ---- tool operations ----
    def search_cards(self, query: str) -> list[dict[str, Any]]:
        q = (query or "").strip().lower()
        if not q:
            return self.cards

        out: list[dict[str, Any]] = []
        for c in self.cards:
            # Make this robust for your new schema
            rewards = c.get("rewards") or {}
            benefits = c.get("benefits") or []

            hay = " ".join(
                [
                    str(c.get("id", "")),
                    str(c.get("name", "")),
                    str(c.get("type", "")),
                    str(c.get("category", "")),
                    # include rewards keys/values
                    " ".join([f"{k}:{v}" for k, v in rewards.items()]),
                    # include benefits text
                    " ".join([str(b) for b in benefits]),
                ]
            ).lower()

            if q in hay:
                out.append(c)

        return out

    def check_eligibility(self, customer_id: str, card_id: str) -> dict[str, Any]:
        customer = self.get_customer(customer_id)
        if not customer:
            return {"eligible": False, "reason": "Customer not found"}

        score = self._customer_credit_score(customer)
        income = self._customer_annual_income(customer)

        # --- Mock rules (USD-based because your mock data uses annual_income like 85000) ---
        if card_id == "platinum":
            if score >= 700 and income >= 75000:
                return {"eligible": True, "reason": "Meets Platinum mock criteria"}
            return {"eligible": False, "reason": "Needs credit_score>=700 and annual_income>=75000"}

        if card_id == "gold":
            if score >= 650 and income >= 50000:
                return {"eligible": True, "reason": "Meets Gold mock criteria"}
            return {"eligible": False, "reason": "Needs credit_score>=650 and annual_income>=50000"}

        return {"eligible": False, "reason": "Unknown card_id"}

    def rewards_estimate(self, monthly_spend_inr: int, card_id: str) -> dict[str, Any]:
        # leaving your estimate logic intact; rename later if you want USD
        spend = max(int(monthly_spend_inr), 0)
        if card_id == "platinum":
            points = int(spend * 1.2)
        elif card_id == "gold":
            points = int(spend * 1.0)
        else:
            points = int(spend * 0.6)

        return {"monthly_spend_inr": spend, "card_id": card_id, "estimated_points": points}

    def compare_cards(self, card_ids: list[str]) -> list[dict[str, Any]]:
        wanted = set(card_ids or [])
        return [c for c in self.cards if c.get("id") in wanted]
