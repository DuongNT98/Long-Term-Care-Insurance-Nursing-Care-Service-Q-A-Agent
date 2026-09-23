"""AgentCore Platform v1.0"""

# Step 5 — ResponseValidateNode (outer post_process slot).
# Attaches the non-suppressible ケアマネジャー referral notice on every output,
# applies an S-5 rate-limit check, and emits the S-4 audit event. No LLM.

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

CARE_MANAGER_REFERRAL_NOTICE = (
    "This guidance is general information only, not an individualized care "
    "determination or medical advice. For your specific care plan or "
    "eligibility decision, please consult your ケアマネジャー (care manager) "
    "or your municipality's long-term care insurance office."
)


class ResponseValidateNode(FunctionNode):
    """Attach the non-suppressible ケアマネジャー referral notice, apply an S-5
    rate-limit check, and emit the S-4 audit event. Outer post_process slot."""

    # S-1: outer boundary node — matches agent.yaml required_trust_level.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, rate_limiter: Any = None):
        # Injectable rate-limit checker (peak-period S-5 control, docs/02_design.md).
        # None = pass-through no-op; production wiring provisions a real limiter.
        self._rate_limiter = rate_limiter

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if self._rate_limiter is not None and not self._rate_limiter.allow(state.get("caller_id")):
            emit_trace_event(
                "response_validate_rate_limited",
                {"correlation_id": state.get("correlation_id")},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ResponseValidateNode: rate limit exceeded (S-5)"],
            }

        emit_trace_event(
            "response_validated",
            {
                "correlation_id": state.get("correlation_id"),
                "has_variation_note": bool(state.get("municipality_variation_note")),
            },
            state,
        )

        return {
            "care_manager_referral_notice": CARE_MANAGER_REFERRAL_NOTICE,
            "formatted_output": state.get("care_service_guidance", ""),
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        # S-3 preservation variant: the referral notice is non-suppressible —
        # verify this node's own output still carries it (self-consistency,
        # not a re-derivation from unrelated state).
        if not state.get("care_manager_referral_notice"):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ResponseValidateNode: non-suppressible care manager referral notice missing"],
            }
        return state
