"""AgentCore Platform v1.0"""

# Step 4 — MunicipalVariationNoteNode (inner subgraph node).
# Appends a municipality-variation note — mandatory and non-suppressible for
# cost/provider answers given without a validated municipality_code — plus the
# WAM NET provider-lookup link. No LLM.

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.municipality_service import WAMNET_URL, build_variation_note


class MunicipalVariationNoteNode(FunctionNode):
    """Attach the mandatory municipality-variation note + WAM NET link. Inner
    subgraph node — trust already authenticated at the outer backbone."""

    # S-1: inner subgraph node — trust authenticated once at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        intent_type = state.get("intent_type", "eligibility")
        municipality_code_valid = bool(state.get("municipality_code_valid", False))

        note = build_variation_note(intent_type, municipality_code_valid)

        emit_trace_event(
            "municipal_variation_note_applied",
            {"correlation_id": state.get("correlation_id"), "note_applied": bool(note)},
            state,
        )

        return {
            "municipality_variation_note": note,
            "wamnet_link": WAMNET_URL,
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        # S-3 preservation variant (security-5layer-checklist.md S-3): verify
        # this node's OWN output still carries the mandatory variation note
        # when the trigger condition holds. Self-consistency check only —
        # never re-derives from unrelated upstream state.
        intent_type = state.get("intent_type", "eligibility")
        municipality_code_valid = bool(state.get("municipality_code_valid", False))
        note = state.get("municipality_variation_note", "")
        if intent_type in ("cost", "provider") and not municipality_code_valid and not note:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["MunicipalVariationNoteNode: mandatory variation note missing from output"],
            }
        return state
