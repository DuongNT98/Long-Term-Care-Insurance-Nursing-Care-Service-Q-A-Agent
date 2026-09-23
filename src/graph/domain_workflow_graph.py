"""AgentCore Platform v1.0 — HCR-C2-054 inner Cat 2 domain workflow.

Care-context extraction -> care-rules retrieval -> municipality-variation note.
Called by CareQaGraphNode.get_subgraph() in src/graph/graph.py.
"""

from typing import Any

from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus

from src.nodes.care_context_extract_node import CareContextExtractNode
from src.nodes.care_rules_retrieve_node import CareRulesRetrieveNode
from src.nodes.municipal_variation_note_node import MunicipalVariationNoteNode
from src.schemas.state import State


class CareRulesWorkflowGraph(BaseGraph):
    """Inner Cat 2 workflow: care-context extraction -> retrieval -> municipality note."""

    @property
    def name(self) -> str:
        return "kaigo_hoken_care_rules_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        pass

    def register_nodes(self) -> None:
        # No super() call — BaseGraph.register_nodes() is abstract. Do NOT
        # register initialize/finalize — outer backbone concern.
        # CareContextExtractNode builds its own (optional) LLM client fresh,
        # per invocation, from caller-bound secrets — see its module docstring.
        self._nodes["care_context_extract"] = CareContextExtractNode()
        self._nodes["care_rules_retrieve"] = CareRulesRetrieveNode()
        self._nodes["municipal_variation_note"] = MunicipalVariationNoteNode()

    def add_edges(self) -> None:
        self._sg.add_edge(START, "care_context_extract")
        self._sg.add_edge("care_context_extract", "care_rules_retrieve")
        self._sg.add_edge("care_rules_retrieve", "municipal_variation_note")
        self._sg.add_edge("municipal_variation_note", END)

    def route(self, state: AgentState) -> str:
        # Required by ABC even for a linear topology (never called unless
        # add_conditional_edges() references it).
        return END if state.get("status") == AgentStatus.ERROR.value else "municipal_variation_note"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        return {
            "care_level": state.get("care_level"),
            "municipality_code": state.get("municipality_code"),
            "municipality_code_valid": state.get("municipality_code_valid"),
            "retrieved_passages": state.get("retrieved_passages", []),
            "kb_source_ref": state.get("kb_source_ref", []),
            "applicable_law_ref": state.get("applicable_law_ref", []),
            "care_service_guidance": state.get("care_service_guidance"),
            "application_steps": state.get("application_steps", []),
            "municipality_variation_note": state.get("municipality_variation_note", ""),
            "wamnet_link": state.get("wamnet_link"),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
