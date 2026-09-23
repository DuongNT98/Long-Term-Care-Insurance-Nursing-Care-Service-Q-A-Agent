# HCR-C2-054 — Unit tests: CareRulesRetrieveNode (step 3, inner subgraph node)

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.care_rules_retrieve_node import CareRulesRetrieveNode
from src.services.care_rules_kb_service import KB_NAMESPACE


class TestCareRulesRetrieveNode:
    def setup_method(self):
        self.node = CareRulesRetrieveNode()

    def test_success_path_yokaigo(self):
        state = {"care_level": "要介護2", "intent_type": "eligibility", "query_text": "eligibility?"}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["retrieved_passages"]
        assert result["kb_source_ref"] == [f"{KB_NAMESPACE}:介護"]
        assert result["applicable_law_ref"]

    def test_procedure_intent_returns_application_steps(self):
        state = {"care_level": "要支援1", "intent_type": "procedure", "query_text": "how do I apply?"}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["application_steps"]

    def test_no_care_level_falls_back_to_general_guidance(self):
        state = {"care_level": None, "intent_type": "eligibility", "query_text": "am I eligible?"}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["kb_source_ref"] == [f"{KB_NAMESPACE}:general"]

    def test_missing_query_text_error(self):
        result = self.node.execute({"care_level": "要介護1", "intent_type": "eligibility", "query_text": ""})
        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]

    def test_trust_gate_declared_anonymous_for_inner_node(self):
        assert CareRulesRetrieveNode.required_trust_level == TrustLevel.ANONYMOUS
