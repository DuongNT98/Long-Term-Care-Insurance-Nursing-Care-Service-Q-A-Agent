# HCR-C2-054 — Unit tests: MunicipalVariationNoteNode (step 4, inner subgraph node)

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.municipal_variation_note_node import MunicipalVariationNoteNode
from src.services.municipality_service import WAMNET_URL


class TestMunicipalVariationNoteNode:
    def setup_method(self):
        self.node = MunicipalVariationNoteNode()

    def test_cost_without_code_gets_mandatory_note(self):
        state = {"intent_type": "cost", "municipality_code_valid": False}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["municipality_variation_note"]
        assert result["wamnet_link"] == WAMNET_URL

    def test_cost_with_valid_code_no_note(self):
        state = {"intent_type": "cost", "municipality_code_valid": True}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["municipality_variation_note"] == ""

    def test_eligibility_intent_no_note(self):
        state = {"intent_type": "eligibility", "municipality_code_valid": False}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["municipality_variation_note"] == ""

    def test_extra_security_gate_output_passthrough_when_note_present(self):
        state = {
            "intent_type": "cost",
            "municipality_code_valid": False,
            "municipality_variation_note": "confirm with your municipality",
        }
        out = self.node._extra_security_gate_output(state)
        assert out is state

    def test_extra_security_gate_output_blocks_when_note_missing(self):
        # Own-dict self-consistency: mandatory note absent from this node's
        # own output when the trigger condition holds -> ERROR, never raise.
        state = {"intent_type": "cost", "municipality_code_valid": False, "municipality_variation_note": ""}
        out = self.node._extra_security_gate_output(state)
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]

    def test_trust_gate_declared_anonymous_for_inner_node(self):
        assert MunicipalVariationNoteNode.required_trust_level == TrustLevel.ANONYMOUS
