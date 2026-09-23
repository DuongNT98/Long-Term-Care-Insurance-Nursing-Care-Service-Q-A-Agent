# HCR-C2-054 — Framework compliance tests TC-01..TC-08.
# Reference shape: adapted from another template's tests/unit/test_framework_compliance.py,
# fitted to this template's real architecture (Cat 2: outer pre/post + GraphNode-wrapped inner nodes).

import json
import os
import re
import typing

import pytest
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.nodes import (
    care_context_extract_node,
    care_rules_retrieve_node,
    municipal_variation_note_node,
    query_normalize_node,
    response_validate_node,
)
from src.schemas.state import State

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
TRUST = TrustLevel.VERIFIED_EXTERNAL.value


def _src_files():
    for root, _d, files in os.walk(_SRC):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


def _unwrap(annotation):
    """Strip NotRequired[...] (and Annotated[...]) to the underlying type."""
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is not None and args:
        return _unwrap(args[0])
    return annotation


# TC-01 - State is a flat TypedDict extending AgentState; agent-specific fields
# are primitives or JSON-serializable list[str]/dict-as-json-string (never
# Pydantic/dataclass/InvocationContext).
class TestTC01StateContract:
    def test_state_is_typeddict_extending_agent_state(self):
        assert hasattr(State, "__annotations__")
        assert "user_input" in State.__annotations__
        assert set(AgentState.__annotations__).issubset(set(State.__annotations__))

    def test_added_fields_are_json_safe(self):
        added = [k for k in State.__annotations__ if k not in AgentState.__annotations__]
        assert added, "State must declare agent-specific fields"
        allowed = {"str", "bool", "list", "int", "float"}
        for name in added:
            base = _unwrap(State.__annotations__[name])
            base_name = getattr(base, "_name", None) or getattr(base, "__name__", str(base))
            assert base_name in allowed, f"{name}: {base_name} — not a JSON-safe primitive/list type"

    def test_added_fields_wrapped_not_required(self):
        # CoE C8 — every agent-specific field must be NotRequired[...] so a
        # checkpoint that pre-dates the field, or a node reading before the
        # writer ran, never KeyErrors.
        added = [k for k in State.__annotations__ if k not in AgentState.__annotations__]
        for name in added:
            raw = State.__annotations__[name]
            assert typing.get_origin(raw) is not None, f"{name} must be wrapped in NotRequired[...]"


# TC-02 - Empty/missing input yields a fail-closed ERROR outcome, no raise.
class TestTC02Validation:
    def test_empty_input_no_raise(self):
        node = query_normalize_node.QueryNormalizeNode()
        out = node.execute({"user_input": "", "input_context": {}})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]

    def test_missing_inner_payload_no_raise(self):
        node = care_context_extract_node.CareContextExtractNode()
        out = node.execute({"user_input": json.dumps({})})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]


# TC-03 - No JWT / API keys / secrets in src/; no direct os.environ reads.
class TestTC03NoCredentials:
    def test_no_credential_literals(self):
        pat = re.compile(r"(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                if pat.search(f.read()):
                    offenders.append(fp)
        assert offenders == []

    def test_no_os_environ_secret_reads(self):
        # S-3: secrets are read via ctx.secrets.require(), never os.environ.
        # Sole exception (the documented entry-point auth exception): the
        # caller-auth token in src/api/server.py, which authenticates the caller
        # BEFORE any InvocationContext exists, so ctx.secrets cannot apply. It is
        # a deployment-level caller credential, not an agent secret.
        entry_point = os.path.join("src", "api", "server.py")
        offenders = []
        for fp in _src_files():
            if os.path.normpath(fp).endswith(entry_point):
                continue
            with open(fp, encoding="utf-8") as f:
                if "os.environ" in f.read():
                    offenders.append(fp)
        assert offenders == []

    def test_entry_point_env_read_is_limited_to_the_caller_auth_token(self):
        """The entry-point exception is narrow: only INVOKE_AUTH_TOKEN may be read."""
        server = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "src",
            "api",
            "server.py",
        )
        if not os.path.exists(server):
            return
        with open(server, encoding="utf-8") as f:
            content = f.read()
        reads = re.findall(r"os\.environ(?:\.get)?[(\[]\s*[\"']([A-Z_]+)[\"']", content)
        assert set(reads) <= {"INVOKE_AUTH_TOKEN"}, f"unexpected env reads: {reads}"


# TC-04 - InvocationContext is never stored in State after invoke.
class TestTC04ContextIsolation:
    def test_no_invocationcontext_in_state_after_invoke(self):
        from src.graph.graph import Graph

        agent = Graph(config={"max_retry": 1})
        agent.compile()
        ctx = InvocationContext(session_id="tc04", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="staff-tc04")
        result = agent.invoke("What are the eligibility rules for 要介護1?", ctx=ctx)
        for v in result.values():
            assert not isinstance(v, InvocationContext)

    def test_from_state_available(self):
        assert hasattr(InvocationContext, "from_state")


# TC-05 - Domain events: every node emits >=1 domain event; no node under
# src/nodes/ ever re-emits a framework backbone lifecycle event.
class TestTC05Audit:
    def test_query_normalize_emits_domain_event(self, monkeypatch):
        events = []
        monkeypatch.setattr(query_normalize_node, "emit_trace_event", lambda e, p, s: events.append(e))
        out = query_normalize_node.QueryNormalizeNode().execute({"user_input": "eligibility?", "input_context": {}})
        assert out["status"] == AgentStatus.SUCCESS
        assert "query_normalized" in events

    def test_response_validate_emits_domain_event(self, monkeypatch):
        events = []
        monkeypatch.setattr(response_validate_node, "emit_trace_event", lambda e, p, s: events.append(e))
        out = response_validate_node.ResponseValidateNode().execute({"care_service_guidance": "g"})
        assert out["status"] == AgentStatus.SUCCESS
        assert "response_validated" in events

    def test_source_has_no_backbone_events(self):
        pat = re.compile(r'emit_trace_event\(\s*["\'](node_start|node_complete|node_error|node_skip)["\']')
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                if pat.search(f.read()):
                    offenders.append(fp)
        assert offenders == []


# TC-06 / TC-07 - S-2/S-3 gates are @final on FunctionNode (overriding raises TypeError at class def).
class TestTC0607FinalGates:
    def test_input_gate_is_final(self):
        with pytest.raises(TypeError):

            class BadIn(FunctionNode):  # noqa: N801
                def _security_gate_input(self, state):
                    return state

    def test_output_gate_is_final(self):
        with pytest.raises(TypeError):

            class BadOut(FunctionNode):  # noqa: N801
                def _security_gate_output(self, result):
                    return result

    def test_extra_hook_is_overridable(self):
        assert (
            municipal_variation_note_node.MunicipalVariationNoteNode._extra_security_gate_output
            is not FunctionNode._extra_security_gate_output
        )
        assert (
            response_validate_node.ResponseValidateNode._extra_security_gate_output
            is not FunctionNode._extra_security_gate_output
        )

    def test_output_gate_blocks_credentials(self):
        # The @final S-3 credential scan actually fires (not vacuous).
        node = response_validate_node.ResponseValidateNode()
        with pytest.raises(Exception):
            node._security_gate_output({"formatted_output": "token AKIAIOSFODNN7EXAMPLE leaked"})


# TC-08 - required_trust_level enforced: insufficient trust -> ERROR state, no raise.
class TestTC08TrustGate:
    def test_declared_trust_levels_valid(self):
        for cls in (
            query_normalize_node.QueryNormalizeNode,
            care_context_extract_node.CareContextExtractNode,
            care_rules_retrieve_node.CareRulesRetrieveNode,
            municipal_variation_note_node.MunicipalVariationNoteNode,
            response_validate_node.ResponseValidateNode,
        ):
            assert cls.required_trust_level in (TrustLevel.ANONYMOUS, TrustLevel.VERIFIED_EXTERNAL, TrustLevel.INTERNAL)

    def test_insufficient_trust_returns_error(self):
        node = query_normalize_node.QueryNormalizeNode()
        out = node({"caller_trust_level": TrustLevel.ANONYMOUS.value, "user_input": "eligibility?", "input_context": {}})
        assert str(out.get("status")).lower().endswith("error")

    def test_sufficient_trust_succeeds(self):
        node = query_normalize_node.QueryNormalizeNode()
        out = node({"caller_trust_level": TRUST, "user_input": "eligibility?", "input_context": {}})
        assert out["status"] == AgentStatus.SUCCESS.value
