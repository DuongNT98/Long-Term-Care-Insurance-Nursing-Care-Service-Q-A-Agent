"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict (see ADR-005 for the prohibited
# alternatives). LangGraph checkpoints use msgpack serialization, so only
# plain serializable fields are allowed. Do NOT add credentials or secrets.

from typing import NotRequired

from framework.schemas.agent_state import AgentState


class State(AgentState):
    """HCR-C2-054 — Long-Term Care Insurance & Nursing Care Service Q&A Agent state.

    All shared fields (user_input, status, session_id, node_history,
    error_log, hitl_*, etc.) are inherited from AgentState. Every
    agent-specific field below is wrapped in NotRequired[...] (CoE C8 —
    absence in the checkpoint or before the writing node runs must not
    KeyError downstream readers, which always use state.get()).
    """

    # mypy cannot see that AgentState is a TypedDict at runtime — the SDK
    # ships no py.typed marker, so framework.schemas.agent_state resolves to
    # Any (see [[tool.mypy.overrides]] in pyproject.toml). Every NotRequired[]
    # field below is therefore individually flagged as "only usable in a
    # TypedDict definition", which is a stub-visibility limitation, not a
    # real type error — the field really is optional/JSON-safe at runtime.

    # Step 1 — QueryNormalizeNode (outer pre_process)
    query_text: NotRequired[str]  # type: ignore[valid-type]
    intent_type: NotRequired[str]  # type: ignore[valid-type]

    # Step 2 — CareContextExtractNode (inner)
    care_level: NotRequired[str]  # type: ignore[valid-type]
    municipality_code: NotRequired[str]  # type: ignore[valid-type]
    municipality_code_valid: NotRequired[bool]  # type: ignore[valid-type]

    # Step 3 — CareRulesRetrieveNode (inner)
    retrieved_passages: NotRequired[list[str]]  # type: ignore[valid-type]
    kb_source_ref: NotRequired[list[str]]  # type: ignore[valid-type]
    applicable_law_ref: NotRequired[list[str]]  # type: ignore[valid-type]
    care_service_guidance: NotRequired[str]  # type: ignore[valid-type]
    application_steps: NotRequired[list[str]]  # type: ignore[valid-type]

    # Step 4 — MunicipalVariationNoteNode (inner)
    municipality_variation_note: NotRequired[str]  # type: ignore[valid-type]
    wamnet_link: NotRequired[str]  # type: ignore[valid-type]

    # Step 5 — ResponseValidateNode (outer post_process)
    care_manager_referral_notice: NotRequired[str]  # type: ignore[valid-type]
