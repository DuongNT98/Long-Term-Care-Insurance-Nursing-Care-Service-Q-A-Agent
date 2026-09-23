# HCR-C2-054 — Unit tests: ResponseValidateNode (step 5, outer post_process)

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.response_validate_node import CARE_MANAGER_REFERRAL_NOTICE, ResponseValidateNode


class DenyingRateLimiter:
    def allow(self, caller_id) -> bool:
        return False


class TestResponseValidateNode:
    def setup_method(self):
        self.node = ResponseValidateNode()

    def test_success_path_attaches_referral_notice(self):
        state = {"care_service_guidance": "General eligibility guidance.", "municipality_variation_note": ""}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["care_manager_referral_notice"] == CARE_MANAGER_REFERRAL_NOTICE
        assert result["formatted_output"] == "General eligibility guidance."

    def test_rate_limited_returns_error(self):
        node = ResponseValidateNode(rate_limiter=DenyingRateLimiter())
        result = node.execute({"care_service_guidance": "guidance", "caller_id": "u1"})
        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]

    def test_extra_security_gate_output_passthrough_when_notice_present(self):
        state = {"care_manager_referral_notice": CARE_MANAGER_REFERRAL_NOTICE}
        out = self.node._extra_security_gate_output(state)
        assert out is state

    def test_extra_security_gate_output_blocks_when_notice_missing(self):
        state = {"care_manager_referral_notice": ""}
        out = self.node._extra_security_gate_output(state)
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]

    def test_trust_gate_declared(self):
        assert ResponseValidateNode.required_trust_level in (
            TrustLevel.ANONYMOUS,
            TrustLevel.VERIFIED_EXTERNAL,
            TrustLevel.INTERNAL,
        )

    def test_insufficient_trust_returns_error(self):
        out = self.node({"caller_trust_level": TrustLevel.ANONYMOUS.value, "care_service_guidance": "g"})
        assert str(out.get("status")).lower().endswith("error")

    def test_sufficient_trust_succeeds(self):
        out = self.node(
            {"caller_trust_level": ResponseValidateNode.required_trust_level.value, "care_service_guidance": "g"}
        )
        assert out["status"] == AgentStatus.SUCCESS.value
