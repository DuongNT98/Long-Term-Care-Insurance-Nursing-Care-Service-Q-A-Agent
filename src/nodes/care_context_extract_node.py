"""AgentCore Platform v1.0"""

# Step 2 — CareContextExtractNode (inner subgraph node).
# Extracts care_level + municipality_code (JIS-validated) to scope retrieval.
# The only node in the pipeline that calls an LLM, and only as a fallback when
# a caller-supplied care_level free-text value cannot be resolved deterministically.
#
# LLM wiring (Azure OpenAI) is opt-in and additive: any failure — missing
# secret, API error, or an LLM reply outside the canonical care-level set —
# degrades to the deterministic baseline (the raw free-text value the caller
# supplied), never raises, and never sets status=error. This node always
# produces a valid result with or without the LLM configured.

import json
from typing import Any, ClassVar, cast

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from shared.services.llm.azure_openai_client import AzureOpenAIClient
from shared.utils.audit_logger import emit_trace_event

from src.services.municipality_service import validate_municipality_code

_VALID_CARE_LEVELS = {
    "要支援1",
    "要支援2",
    "要介護1",
    "要介護2",
    "要介護3",
    "要介護4",
    "要介護5",
}


class CareContextExtractNode(FunctionNode):
    """Extract + validate care_level and municipality_code to scope the
    retrieval step. Inner subgraph node — trust is already authenticated at
    the outer backbone."""

    # S-1: inner subgraph node — trust authenticated once at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = None):
        # Test-double seam only — production wiring (register_nodes()) never
        # passes one. Caching a real client here would be built from whichever
        # caller happened to construct this node instance and then reused
        # across every later invocation (node instances are constructed once
        # and reused via the registry's LRU cache), leaking one caller's
        # secret-bound client to the next. The real client is built fresh,
        # per invocation, inside execute() instead.
        self._llm = llm

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("user_input", "")
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            payload = None

        if not isinstance(payload, dict) or not payload.get("query_text"):
            emit_trace_event(
                "care_context_extract_failed",
                {"correlation_id": state.get("correlation_id"), "reason": "no_query_text"},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["CareContextExtractNode: no query_text in inner input"],
            }

        query_text = payload["query_text"]
        care_level = payload.get("care_level")
        municipality_code = payload.get("municipality_code")

        if care_level and care_level not in _VALID_CARE_LEVELS:
            # Free-text care_level supplied — ask the LLM to normalize it to a
            # canonical value. Deterministic matching failed upstream; on any
            # failure keep the raw free-text value (the same result this node
            # already produced before the LLM was wired in).
            normalized = self._normalize_care_level(care_level, state)
            if normalized is not None:
                care_level = normalized

        municipality_code_valid = bool(municipality_code) and validate_municipality_code(cast(str, municipality_code))

        emit_trace_event(
            "care_context_extracted",
            {
                "correlation_id": state.get("correlation_id"),
                "care_level": care_level,
                "municipality_code_valid": municipality_code_valid,
            },
            state,
        )

        return {
            "query_text": query_text,
            "intent_type": payload.get("intent_type", "eligibility"),
            "care_level": care_level,
            "municipality_code": municipality_code,
            "municipality_code_valid": municipality_code_valid,
            "status": AgentStatus.SUCCESS.value,
        }

    def _normalize_care_level(self, care_level: str, state: dict[str, Any]) -> str | None:
        """Best-effort LLM normalization of a free-text care level to one of
        _VALID_CARE_LEVELS. Returns None (never raises) on a missing secret,
        an API error, or a reply outside the canonical set — the caller keeps
        the raw free-text value in that case."""
        try:
            llm = self._llm
            if llm is None:
                ctx = InvocationContext.from_state(state)
                llm = AzureOpenAIClient(
                    {
                        "api_key": ctx.secrets.require("AZURE_OPENAI_API_KEY"),
                        "azure_endpoint": ctx.secrets.require("AZURE_OPENAI_ENDPOINT"),
                        "azure_deployment": ctx.secrets.require("AZURE_OPENAI_DEPLOYMENT"),
                    }
                )
            response = llm.complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "You normalize a Japanese long-term care insurance care level to "
                            "exactly one canonical value. Reply with ONLY that value, nothing else."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Normalize this care level to one of {sorted(_VALID_CARE_LEVELS)}: {care_level}",
                    },
                ]
            )
            normalized = response.get("content", "").strip() if isinstance(response, dict) else ""
            # Never surface an unvalidated LLM reply into state — reject anything
            # outside the canonical set exactly as if the LLM had not been called.
            return normalized if normalized in _VALID_CARE_LEVELS else None
        except Exception:
            return None
