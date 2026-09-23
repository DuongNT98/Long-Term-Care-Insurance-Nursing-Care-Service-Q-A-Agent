# PB-6 (GraphNode boundary) - review-and-fix-code #407 proactive audit.
#
# PB-6 (test_pb_invoke_order.py) only discovers concrete BaseNode subclasses
# under src/nodes/. CareQaGraphNode lives in src/graph/graph.py (the correct
# location for the outer `main`-slot GraphNode wrapper, per scaffold
# canonical), which puts it outside PB-6's discovery scope. That placement is
# architecturally correct - but does NOT exempt it from a security-boundary
# test: it is the first node the outer backbone hands caller input to. This
# file closes that test-scope blind spot.

import pytest

from framework.schemas.trust_level import TrustLevel

from src.graph.graph import CareQaGraphNode


class TestGraphNodeTrustGate:
    """S-1: the outer main-slot GraphNode enforces the trust gate like any other node."""

    def test_insufficient_trust_denied_before_subgraph_dispatch(self):
        node = CareQaGraphNode()
        state = {
            "caller_trust_level": TrustLevel.ANONYMOUS.value,
            "user_input": "{\"query_text\": \"What are the eligibility rules?\"}",
            "correlation_id": "pb6-graphnode-boundary-test",
        }
        out = node(state)
        assert str(out.get("status")).lower().endswith("error")
        assert any("S-1 trust gate denied" in e for e in out.get("error_log", []))

    def test_declared_trust_level_matches_agent_default(self):
        # Outer GraphNode main-slot must match agent.yaml's declared default
        # (VERIFIED_EXTERNAL) - "it just delegates to inner so it doesn't need to
        # declare" is wrong (security-5layer-checklist.md S-1).
        assert CareQaGraphNode.required_trust_level == TrustLevel.VERIFIED_EXTERNAL


class TestGraphNodeBoundaryMapping:
    """Criterion #9: extract_input()/merge_output() map fields explicitly, no raw pass-through."""

    def test_extract_input_returns_only_the_contracted_field(self):
        node = CareQaGraphNode()
        state = {
            "validated_input": '{"query_text": "cost question", "care_level": "要介護1"}',
            "user_input": "raw caller text should not leak through if validated_input is present",
            "correlation_id": "pb6-graphnode-boundary-test",
        }
        result = node.extract_input(state)
        assert result == state["validated_input"]

    def test_merge_output_maps_fields_explicitly_not_raw_passthrough(self):
        node = CareQaGraphNode()
        sub_result = {
            "care_level": "要介護1",
            "municipality_code": "131016",
            "municipality_code_valid": True,
            "retrieved_passages": ["passage 1"],
            "kb_source_ref": ["ref-1"],
            "applicable_law_ref": ["law-1"],
            "care_service_guidance": "guidance text",
            "application_steps": ["step 1"],
            "municipality_variation_note": "",
            "wamnet_link": None,
            "status": "success",
            "internal_debug_field_not_in_contract": "must not leak into parent state",
        }
        merged = node.merge_output({}, sub_result)
        assert "internal_debug_field_not_in_contract" not in merged
        assert merged["care_level"] == sub_result["care_level"]
        assert merged["status"] == sub_result["status"]


class TestGraphNodeDelegatedGating:
    """Delegation is a deliberate design choice: the inner entry node still carries S-2/S-3 gates."""

    def test_inner_entry_node_is_a_gated_function_node(self):
        # CareQaGraphNode.__call__ intentionally skips the standard S-2/S-4/S-3
        # lifecycle (see framework/nodes/graph_node.py) because gating is delegated to
        # the inner subgraph's own entry node, which is a full FunctionNode and
        # therefore still runs _security_gate_input()/_security_gate_output() (both
        # @final) on every invocation.
        from framework.nodes.function_node import FunctionNode

        from src.nodes.care_context_extract_node import CareContextExtractNode

        assert issubclass(CareContextExtractNode, FunctionNode)


@pytest.fixture(autouse=True)
def _skip_if_stale_local_wheel():
    import framework.nodes.base_node as base_node_module

    if not hasattr(base_node_module, "emit_trace_event"):
        pytest.skip("local wheel rc1 stale (missing emit_trace_event) - CI wheel 1.0.0 is the gate of record")
