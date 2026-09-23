# HCR-C2-054 — Unit tests: CareContextExtractNode (step 2, inner subgraph node)

import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.care_context_extract_node import CareContextExtractNode


class FakeLLM:
    def __init__(self, reply: str = "要介護2", raises: bool = False):
        self._reply = reply
        self._raises = raises

    def complete(self, messages: list) -> dict:
        if self._raises:
            raise RuntimeError("simulated Azure OpenAI API error")
        return {"content": self._reply}


class TestCareContextExtractNode:
    def setup_method(self):
        self.node = CareContextExtractNode()

    def _payload(self, **overrides) -> str:
        base = {"query_text": "eligibility question", "intent_type": "eligibility", "care_level": None, "municipality_code": None}
        base.update(overrides)
        return json.dumps(base, ensure_ascii=False)

    def test_success_path_with_valid_care_level_and_code(self):
        state = {"user_input": self._payload(care_level="要介護1", municipality_code="131016")}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["care_level"] == "要介護1"
        assert result["municipality_code_valid"] is True

    def test_invalid_municipality_code_shape(self):
        state = {"user_input": self._payload(municipality_code="ABC")}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["municipality_code_valid"] is False

    def test_missing_query_text_error(self):
        result = self.node.execute({"user_input": json.dumps({})})
        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]

    def test_llm_normalizes_free_text_care_level(self):
        node = CareContextExtractNode(llm=FakeLLM(reply="要介護2"))
        state = {"user_input": self._payload(care_level="level two nursing care")}
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["care_level"] == "要介護2"

    def test_llm_reply_outside_canonical_set_falls_back_to_raw_text(self):
        # An unvalidated LLM reply must never reach state — reject it exactly
        # as if the LLM had not been called.
        node = CareContextExtractNode(llm=FakeLLM(reply="not a real care level"))
        state = {"user_input": self._payload(care_level="level two nursing care")}
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["care_level"] == "level two nursing care"

    def test_llm_raising_falls_back_to_raw_text(self):
        node = CareContextExtractNode(llm=FakeLLM(raises=True))
        state = {"user_input": self._payload(care_level="level two nursing care")}
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["care_level"] == "level two nursing care"

    def test_no_llm_injected_and_no_secrets_bound_falls_back_to_raw_text(self):
        # The real production shape in any environment without a configured
        # Azure key: no llm= injected, and building InvocationContext/secrets
        # from this bare state fails — must degrade, never raise.
        node = CareContextExtractNode()
        state = {"user_input": self._payload(care_level="level two nursing care")}
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["care_level"] == "level two nursing care"

    def test_valid_care_level_never_calls_the_llm(self):
        class ExplodingLLM:
            def complete(self, messages: list) -> dict:
                raise AssertionError("LLM must not be called for an already-valid care_level")

        node = CareContextExtractNode(llm=ExplodingLLM())
        state = {"user_input": self._payload(care_level="要介護1")}
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["care_level"] == "要介護1"

    def test_no_care_level_never_calls_the_llm(self):
        class ExplodingLLM:
            def complete(self, messages: list) -> dict:
                raise AssertionError("LLM must not be called when no care_level is supplied")

        node = CareContextExtractNode(llm=ExplodingLLM())
        state = {"user_input": self._payload()}
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["care_level"] is None

    def test_trust_gate_declared_anonymous_for_inner_node(self):
        # Inner subgraph node — trust already authenticated at the outer backbone.
        assert CareContextExtractNode.required_trust_level == TrustLevel.ANONYMOUS
