"""AgentCore Platform v1.0"""

# Step 3 — CareRulesRetrieveNode (inner subgraph node).
# Retrieves from 介護保険法 + MHLW guidance + 区分支給限度基準額/介護報酬単価 tables +
# WAM NET (namespace `kaigo_hoken_rules`). Deterministic retrieval only — no LLM.

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.care_rules_kb_service import CareRulesKBService


class CareRulesRetrieveNode(FunctionNode):
    """Retrieve care-rule passages, law references, and application steps for
    the scoped care_level + intent_type. Inner subgraph node."""

    # S-1: inner subgraph node — trust authenticated once at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, kb_service: CareRulesKBService | None = None):
        self._kb_service = kb_service or CareRulesKBService()

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        care_level = state.get("care_level")
        intent_type = state.get("intent_type", "eligibility")
        query_text = state.get("query_text", "")

        if not query_text:
            emit_trace_event(
                "care_rules_retrieve_failed",
                {"correlation_id": state.get("correlation_id"), "reason": "no_query_text"},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["CareRulesRetrieveNode: no query_text to retrieve for"],
            }

        result = self._kb_service.retrieve(care_level=care_level, intent_type=intent_type, query_text=query_text)

        emit_trace_event(
            "care_rules_retrieved",
            {
                "correlation_id": state.get("correlation_id"),
                "passage_count": len(result.passages),
                "care_level": care_level,
            },
            state,
        )

        return {
            "retrieved_passages": result.passages,
            "kb_source_ref": result.kb_source_ref,
            "applicable_law_ref": result.applicable_law_ref,
            "care_service_guidance": result.guidance_text,
            "application_steps": result.application_steps,
            "status": AgentStatus.SUCCESS.value,
        }
