"""Token shape, uniqueness and randomness, and the pure verification checks."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from module_7.services.tokens import ALPHABET, LENGTH, looks_like_token, new_token
from module_7.services.verification import checks


def test_ten_thousand_tokens_are_well_formed_and_unique() -> None:
    tokens = [new_token() for _ in range(10_000)]
    assert all(len(t) == LENGTH == 12 for t in tokens)
    assert all(looks_like_token(t) for t in tokens)
    assert len(set(tokens)) == 10_000


def test_characters_are_spread_evenly() -> None:
    """A crude entropy check: 120,000 characters over 32 symbols, about 3,750 each."""
    counts = Counter("".join(new_token() for _ in range(10_000)))
    assert set(counts) == set(ALPHABET)
    assert all(3_300 < c < 4_200 for c in counts.values()), counts
    first = Counter(t[0] for t in (new_token() for _ in range(3_200)))
    assert len(first) == 32  # no fixed prefix


def test_tokens_are_not_derived_from_anything() -> None:
    assert new_token() != new_token()
    assert not looks_like_token("BWP-G1-H01-001")
    assert not looks_like_token("abcdefghijkl")  # lower case is not the alphabet
    assert not looks_like_token("ABCDEFGHIJK1")  # 1 is not base32


def _checks(**over):  # type: ignore[no-untyped-def]
    base = {
        "fieldbook_statuses": ["submitted", "submitted"],
        "deliveries": [("delivered", 100.0)],
        "heap_status": "closed",
        "bales_weight_kg": Decimal(340),
        "expected_output_kg": Decimal(340),
    }
    return {c.key: c.passed for c in checks(**{**base, **over})}


def test_verification_checks_flip() -> None:
    assert all(_checks().values())
    assert _checks(fieldbook_statuses=["submitted", "draft"])["fieldbooks_submitted"] is False
    assert _checks(fieldbook_statuses=["submitted", None])["fieldbooks_submitted"] is False
    assert (
        _checks(deliveries=[("delivered", 100.0), ("in_transit", None)])["deliveries_weighed"]
        is False
    )
    assert _checks(deliveries=[("delivered", None)])["deliveries_weighed"] is False
    assert _checks(heap_status="open")["heap_closed"] is False
    assert _checks(bales_weight_kg=Decimal(341))["mass_balance"] is False
    assert _checks(fieldbook_statuses=[], deliveries=[])["fieldbooks_submitted"] is False
