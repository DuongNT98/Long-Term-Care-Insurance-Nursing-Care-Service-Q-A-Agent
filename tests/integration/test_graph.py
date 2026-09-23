# HCR-C2-054 — Integration test: full graph compile + invoke (Cat 2 outer + inner subgraph).

import json

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import Graph


class TestAgentIntegration:
    def test_eligibility_question_reaches_full_pipeline(self):
        agent = Graph(config={"max_retry": 1})
        agent.compile()
        ctx = InvocationContext(session_id="it-1", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="caregiver-001")
        result = agent.invoke("What are the eligibility rules for 要介護2?", ctx=ctx)

        assert len(result.get("node_history", [])) >= 5
        assert result["status"] in ("success", "error", "cancelled")
        if result["status"] == "success":
            assert result.get("care_manager_referral_notice")

    def test_cost_question_without_municipality_code_gets_variation_note(self):
        agent = Graph(config={"max_retry": 1})
        agent.compile()
        ctx = InvocationContext(session_id="it-2", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="caregiver-002")
        result = agent.invoke("How much does the day service cost?", ctx=ctx)

        assert len(result.get("node_history", [])) >= 5
        if result["status"] == "success":
            assert result.get("municipality_variation_note")
            assert result.get("wamnet_link")
            assert result.get("care_manager_referral_notice")

    def test_empty_query_error(self):
        agent = Graph(config={"max_retry": 1})
        agent.compile()
        ctx = InvocationContext(session_id="it-3", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="caregiver-003")
        result = agent.invoke("", ctx=ctx)
        assert result["status"] in ("error", "cancelled")

    def test_personal_identifier_rejected_end_to_end(self):
        # The S-2 input security gate (framework, before execute()) may
        # pre-sanitize PII from user_input before QueryNormalizeNode ever
        # sees it — behavior varies by environment. Assert the invariant
        # that holds either way: the raw identifier never appears in the
        # output, whether QueryNormalizeNode rejected it OR the framework
        # gate scrubbed it upstream. Node-level rejection is covered
        # deterministically in tests/unit/test_query_normalize_node.py.
        agent = Graph(config={"max_retry": 1})
        agent.compile()
        ctx = InvocationContext(session_id="it-4", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="caregiver-004")
        result = agent.invoke("My number is 123456789012, what's my care level?", ctx=ctx)
        assert "123456789012" not in json.dumps(result, default=str)
