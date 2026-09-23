"""AgentCore Platform v1.0"""

# Step 1 — QueryNormalizeNode (outer pre_process slot).
# Sanitizes the query, rejects care-recipient personal data (S-1), classifies
# intent type. No LLM — deterministic only.

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.query_sanitizer_service import (
    classify_intent,
    contains_personal_identifier,
    sanitize_query,
)


class QueryNormalizeNode(FunctionNode):
    """Sanitize the query, reject care-recipient personal data (S-1), classify
    intent type, and hand a JSON envelope to the inner Cat 2 subgraph."""

    # S-1: outer boundary node — matches agent.yaml required_trust_level.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")
        input_context = state.get("input_context", {})

        if not user_input or not user_input.strip():
            emit_trace_event(
                "query_normalize_rejected",
                {"correlation_id": state.get("correlation_id"), "reason": "empty_input"},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["QueryNormalizeNode: user_input is empty or missing"],
            }

        if contains_personal_identifier(user_input):
            emit_trace_event(
                "query_normalize_rejected",
                {"correlation_id": state.get("correlation_id"), "reason": "personal_data_detected"},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [
                    "QueryNormalizeNode: query appears to contain a care-recipient "
                    "personal identifier (e.g. My Number). This agent does not accept "
                    "individual identifiers (S-1) — please rephrase without personal data."
                ],
            }

        # S-2: input_context is a tenant-supplied nested dict, not a plain
        # framework-scanned string field. care_level in particular can reach
        # an LLM prompt downstream (CareContextExtractNode's free-text
        # normalization fallback) when it fails the enum whitelist check —
        # that enum check is a format/schema check, not a content-security
        # scan, so run the same PII scan used on user_input over every
        # string value here before it is allowed to flow further.
        for _key, _val in input_context.items():
            if isinstance(_val, str) and contains_personal_identifier(_val):
                emit_trace_event(
                    "query_normalize_rejected",
                    {
                        "correlation_id": state.get("correlation_id"),
                        "reason": "personal_data_detected_in_input_context",
                        "field": _key,
                    },
                    state,
                )
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": [
                        f"QueryNormalizeNode: input_context.{_key} appears to contain a "
                        "care-recipient personal identifier (e.g. My Number). This agent "
                        "does not accept individual identifiers (S-1) — please rephrase "
                        "without personal data."
                    ],
                }

        query_text = sanitize_query(user_input)
        intent_type = classify_intent(query_text)
        care_level = input_context.get("care_level")
        municipality_code = input_context.get("municipality_code")

        payload = {
            "query_text": query_text,
            "intent_type": intent_type,
            "care_level": care_level,
            "municipality_code": municipality_code,
        }

        emit_trace_event(
            "query_normalized",
            {"correlation_id": state.get("correlation_id"), "intent_type": intent_type},
            state,
        )

        return {
            "query_text": query_text,
            "intent_type": intent_type,
            "validated_input": json.dumps(payload, ensure_ascii=False),
            "status": AgentStatus.SUCCESS.value,
        }
