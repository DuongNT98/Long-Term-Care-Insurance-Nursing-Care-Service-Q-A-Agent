# HCR-C2-054 — Unit tests: QueryNormalizeNode (step 1, outer pre_process)

import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.query_normalize_node import QueryNormalizeNode


class TestQueryNormalizeNode:
    def setup_method(self):
        self.node = QueryNormalizeNode()

    def test_success_path(self):
        state = {"user_input": "  What are the eligibility rules for 要介護1?  ", "input_context": {}}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["query_text"] == "What are the eligibility rules for 要介護1?"
        payload = json.loads(result["validated_input"])
        assert payload["query_text"] == result["query_text"]
        assert payload["intent_type"] == result["intent_type"]

    def test_carries_optional_care_context_from_input_context(self):
        state = {
            "user_input": "How much does day care cost?",
            "input_context": {"care_level": "要介護2", "municipality_code": "131016"},
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        payload = json.loads(result["validated_input"])
        assert payload["care_level"] == "要介護2"
        assert payload["municipality_code"] == "131016"
        assert result["intent_type"] == "cost"

    def test_empty_input_error(self):
        result = self.node.execute({"user_input": "", "input_context": {}})
        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]

    def test_personal_identifier_rejected(self):
        # 12-digit sequence shaped like a My Number must be rejected (S-1).
        result = self.node.execute({"user_input": "My number is 123456789012, what's my care level?", "input_context": {}})
        assert result["status"] == AgentStatus.ERROR
        assert "personal" in result["error_log"][0].lower()

    def test_personal_identifier_in_input_context_rejected(self):
        # S-2: input_context is a tenant-supplied nested dict — care_level in
        # particular can reach an LLM prompt downstream when it fails the
        # enum whitelist (CareContextExtractNode's free-text normalization
        # fallback), so a My Number-shaped value smuggled through
        # input_context.care_level must be rejected here too, not just on
        # user_input.
        result = self.node.execute(
            {
                "user_input": "What are the eligibility rules?",
                "input_context": {"care_level": "123456789012"},
            }
        )
        assert result["status"] == AgentStatus.ERROR
        assert "input_context.care_level" in result["error_log"][0]

    def test_trust_gate_declared(self):
        assert QueryNormalizeNode.required_trust_level in (
            TrustLevel.ANONYMOUS,
            TrustLevel.VERIFIED_EXTERNAL,
            TrustLevel.INTERNAL,
        )

    def test_insufficient_trust_returns_error(self):
        out = self.node({"caller_trust_level": TrustLevel.ANONYMOUS.value, "user_input": "eligibility?", "input_context": {}})
        assert str(out.get("status")).lower().endswith("error")

    def test_sufficient_trust_succeeds(self):
        out = self.node(
            {
                "caller_trust_level": QueryNormalizeNode.required_trust_level.value,
                "user_input": "eligibility?",
                "input_context": {},
            }
        )
        assert out["status"] == AgentStatus.SUCCESS.value
