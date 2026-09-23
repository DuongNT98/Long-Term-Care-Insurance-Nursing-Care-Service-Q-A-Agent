"""AgentCore Platform v1.0 — HCR-C2-054 domain service.

Deterministic query sanitization + intent classification helpers used by
QueryNormalizeNode (S-1 — no care-recipient personal data allowed).
"""

from __future__ import annotations

import re

# A crude but effective screen for individually-identifying numbers.
# Japan's My Number (individual number) is a 12-digit number.
_MY_NUMBER_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")

_COST_KEYWORDS = ("cost", "price", "yen", "円", "自己負担", "費用", "料金")
_PROVIDER_KEYWORDS = ("provider", "facility", "事業所", "施設")
_PROCEDURE_KEYWORDS = ("apply", "application", "procedure", "申請", "手続き")


def contains_personal_identifier(text: str) -> bool:
    """Return True if the text looks like it embeds an individual identifier
    (e.g. a My Number-shaped 12-digit sequence).

    Best-effort heuristic, documented in docs/02_design.md as an S-1 guard —
    not exhaustive PII detection.
    """
    return bool(_MY_NUMBER_RE.search(text))


def sanitize_query(text: str) -> str:
    """Trim + collapse whitespace. Domain-specific normalization extension point."""
    return " ".join(text.strip().split())


def classify_intent(query_text: str) -> str:
    """Best-effort keyword classification into cost / provider / procedure / eligibility.

    This is a deterministic first pass; CareContextExtractNode may refine the
    scope with an LLM in step 2 when the free text is ambiguous.
    """
    if any(kw in query_text for kw in _COST_KEYWORDS):
        return "cost"
    if any(kw in query_text for kw in _PROVIDER_KEYWORDS):
        return "provider"
    if any(kw in query_text for kw in _PROCEDURE_KEYWORDS):
        return "procedure"
    return "eligibility"
