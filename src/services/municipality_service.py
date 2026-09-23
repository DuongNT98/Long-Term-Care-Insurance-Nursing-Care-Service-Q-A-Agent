"""AgentCore Platform v1.0 — HCR-C2-054 domain service.

JIS local-government-code validation + WAM NET reference link used by the
municipality-variation gate (docs/02_design.md).
"""

from __future__ import annotations

import re

# JIS X 0402 local government code: 6 digits (5-digit body + 1 check digit).
_JIS_CODE_RE = re.compile(r"^\d{6}$")

WAMNET_URL = "https://www.wam.go.jp/content/wamnet/pcpub/top/"


def validate_municipality_code(code: str) -> bool:
    """Return True when `code` is shaped like a valid JIS X 0402 local
    government code (6 numeric digits).

    This is a format check, not a lookup against the live JIS registry —
    extension point documented in docs/02_design.md.
    """
    if not isinstance(code, str):
        return False
    return bool(_JIS_CODE_RE.match(code.strip()))


def build_variation_note(intent_type: str, municipality_code_valid: bool) -> str:
    """Non-suppressible municipality-variation note: mandatory whenever a
    cost/provider answer is given without a validated municipality_code.
    """
    if intent_type in ("cost", "provider") and not municipality_code_valid:
        return (
            "Actual out-of-pocket costs and available providers vary by municipality. "
            "Please confirm the current figures with your municipality's long-term "
            f"care insurance office, or search current providers on WAM NET: {WAMNET_URL}"
        )
    return ""
