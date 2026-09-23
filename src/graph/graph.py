"""AgentCore Platform v1.0 — HCR-C2-054 outer Cat 2 graph.

Outer backbone (fixed): initialize -> pre_process -> main -> post_process -> finalize.
The `main` slot wraps the inner care-rules workflow subgraph
(src/graph/domain_workflow_graph.py). The GraphNode wrapper class lives in
THIS file (not src/nodes/), per the framework's Cat 2 composition pattern:
PB-6 (tests/proof_of_boundary/test_pb_invoke_order.py) auto-discovers every
BaseNode subclass under src/nodes/, but GraphNode.__call__() intentionally
skips that lifecycle (it delegates gating to the inner subgraph), so placing
it under src/nodes/ would false-fail PB-6.
"""

from typing import TYPE_CHECKING, Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.nodes.query_normalize_node import QueryNormalizeNode
from src.nodes.response_validate_node import ResponseValidateNode
from src.schemas.state import State

if TYPE_CHECKING:
    from src.graph.domain_workflow_graph import CareRulesWorkflowGraph


class CareQaGraphNode(GraphNode):
    """Wraps the inner care-rules workflow subgraph (steps 2-4: care-context
    extraction, retrieval, municipality-variation note); assigned to the
    outer `main` slot."""

    # S-1: outer main-slot GraphNode — matches agent.yaml required_trust_level.
    # The lifecycle-skip docstring above (GraphNode.__call__ delegates gating
    # to the inner subgraph) does not substitute for this declaration.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL
    error_strategy: ClassVar[str] = "propagate"
    propagate_hitl: ClassVar[bool] = False

    def execute(self, state: AgentState) -> dict[str, Any]:
        # The outer pre_process -> main edge is unconditional (AgentBaseGraph
        # default routing), so a QueryNormalizeNode rejection (empty input /
        # personal identifier, status=ERROR) would otherwise still reach here
        # and extract_input() would fall back to the raw, unvalidated
        # user_input. Re-check the same precondition before dispatching to
        # the inner subgraph.
        if state.get("status") == AgentStatus.ERROR.value:
            return {
                "status": state.get("status"),
                "error_log": state.get("error_log", []),
            }
        # super().execute() resolves to Any — GraphNode is SDK-provided and
        # ships no py.typed marker (see [[tool.mypy.overrides]]).
        return cast(dict[str, Any], super().execute(state))

    def get_subgraph(self) -> "CareRulesWorkflowGraph":
        from src.graph.domain_workflow_graph import CareRulesWorkflowGraph

        sg = CareRulesWorkflowGraph()
        sg.compile()
        return sg

    def extract_input(self, state: AgentState) -> str:
        # S-4: runs inside GraphNode.execute() — audit the dispatch into the inner subgraph.
        emit_trace_event(
            "care_rules_workflow_dispatched",
            {"correlation_id": state.get("correlation_id")},
            state,
        )
        return cast(str, state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        # S-4: runs inside GraphNode.execute() — audit the subgraph outcome merged back out.
        emit_trace_event(
            "care_rules_workflow_completed",
            {
                "correlation_id": state.get("correlation_id"),
                "passage_count": len(sub_result.get("retrieved_passages", [])),
            },
            state,
        )
        return {
            "care_level": sub_result.get("care_level"),
            "municipality_code": sub_result.get("municipality_code"),
            "municipality_code_valid": sub_result.get("municipality_code_valid"),
            "retrieved_passages": sub_result.get("retrieved_passages", []),
            "kb_source_ref": sub_result.get("kb_source_ref", []),
            "applicable_law_ref": sub_result.get("applicable_law_ref", []),
            "care_service_guidance": sub_result.get("care_service_guidance"),
            "application_steps": sub_result.get("application_steps", []),
            "municipality_variation_note": sub_result.get("municipality_variation_note", ""),
            "wamnet_link": sub_result.get("wamnet_link"),
            "status": sub_result.get("status"),
        }


class HcrLtcQaGraph(AgentBaseGraph):
    """HCR-C2-054 — Long-Term Care Insurance & Nursing Care Service Q&A Agent."""

    @property
    def name(self) -> str:
        return "hcr-c2-054"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects InitializeNode + FinalizeNode
        self._nodes["pre_process"] = QueryNormalizeNode()
        self._nodes["main"] = CareQaGraphNode()
        self._nodes["post_process"] = ResponseValidateNode()

    def get_output(self, state: AgentState) -> dict[str, Any]:
        # AgentBaseGraph's default get_output() only surfaces "output"
        # (formatted_output/result) — the caller also needs the non-suppressible
        # referral notice, the municipality-variation note, and source
        # attribution to act on the answer.
        base = super().get_output(state)
        return {
            **base,
            "care_manager_referral_notice": state.get("care_manager_referral_notice"),
            "municipality_variation_note": state.get("municipality_variation_note", ""),
            "wamnet_link": state.get("wamnet_link"),
            "kb_source_ref": state.get("kb_source_ref", []),
            "applicable_law_ref": state.get("applicable_law_ref", []),
        }


Graph = HcrLtcQaGraph  # alias for agent.yaml module: "src.graph"
