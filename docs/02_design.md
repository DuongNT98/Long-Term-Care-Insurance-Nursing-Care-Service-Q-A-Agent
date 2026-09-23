# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `HcrLtcQaGraph`
- **L1 Base**: AgentBaseGraph
- **Three-Layer Separation**:
  - State: flat TypedDict composition (`src/schemas/state.py`, no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Architecture Overview — Cat 2 (outer AgentBaseGraph + GraphNode + inner subgraph)

This template is **Cat 2**: a fixed 5-node outer backbone wraps a domain-specific
inner workflow inside the `main` slot via a `GraphNode` (`CareQaGraphNode`,
`src/graph/graph.py`), which dispatches to an inner `BaseGraph`
(`CareRulesWorkflowGraph`, `src/graph/domain_workflow_graph.py`).

### Node Configuration — outer

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | schema_version, session_id, trust_level | — | — | InitializeNode (default) |
| pre_process | Step 1 — `QueryNormalizeNode`: sanitize input, reject care-recipient personal data (S-1), classify intent | `user_input`, `input_context` | `query_text`, `intent_type`, `validated_input` | FunctionNode |
| main | `CareQaGraphNode` (GraphNode) — dispatches steps 2-4 to the inner subgraph | `validated_input` | `care_level`, `municipality_code`, `municipality_code_valid`, `retrieved_passages`, `kb_source_ref`, `applicable_law_ref`, `care_service_guidance`, `application_steps`, `municipality_variation_note`, `wamnet_link` | GraphNode |
| post_process | Step 5 — `ResponseValidateNode`: attach non-suppressible ケアマネジャー referral notice, S-5 rate-limit check | `care_service_guidance`, `municipality_variation_note` | `care_manager_referral_notice`, `formatted_output` | FunctionNode |
| finalize | response_metadata, total_time_ms | — | — | FinalizeNode (default) |

### Node Configuration — inner (`CareRulesWorkflowGraph`)

| Inner node | Responsibility | Input | Output | LLM |
|---|---|---|---|---|
| care_context_extract | Step 2 — `CareContextExtractNode`: extract + JIS-validate care_level/municipality_code | `user_input` (JSON envelope from outer `validated_input`) | `care_level`, `municipality_code`, `municipality_code_valid` | ✅ fallback only, for free-text care_level normalization (Azure OpenAI, built fresh per invocation — see below) |
| care_rules_retrieve | Step 3 — `CareRulesRetrieveNode`: retrieve from `kaigo_hoken_rules` KB namespace | `care_level`, `intent_type`, `query_text` | `retrieved_passages`, `kb_source_ref`, `applicable_law_ref`, `care_service_guidance`, `application_steps` | ❌ |
| municipal_variation_note | Step 4 — `MunicipalVariationNoteNode`: mandatory municipality-variation note + WAM NET link | `intent_type`, `municipality_code_valid` | `municipality_variation_note`, `wamnet_link` | ❌ |

### Data Flow

```
Outer: START → initialize → pre_process → main(GraphNode) → {route} → post_process → finalize → END
                                              │ extract_input() -> validated_input (JSON string)
                                              ▼
Inner: START → care_context_extract → care_rules_retrieve → municipal_variation_note → END
                                              │ merge_output() maps sub_result back into outer state
```

The inner subgraph never sees the outer `AgentState` directly — only the string
returned by `CareQaGraphNode.extract_input()` (the JSON envelope built by
`QueryNormalizeNode`). `merge_output()` maps only the changed keys back.

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| query_text | `NotRequired[str]` | Sanitized query text (step 1) | No |
| intent_type | `NotRequired[str]` | `eligibility` / `cost` / `provider` / `procedure` (step 1) | No |
| care_level | `NotRequired[str]` | 要支援1/2, 要介護1-5 (step 2) | No |
| municipality_code | `NotRequired[str]` | JIS X 0402 local-government code (step 2) | No |
| municipality_code_valid | `NotRequired[bool]` | Format-validated flag (step 2) | No |
| retrieved_passages | `NotRequired[list[str]]` | Retrieved KB passages (step 3) | No |
| kb_source_ref | `NotRequired[list[str]]` | KB namespace/bucket reference (step 3) | No |
| applicable_law_ref | `NotRequired[list[str]]` | 介護保険法 / MHLW references (step 3) | No |
| care_service_guidance | `NotRequired[str]` | Assembled guidance text (step 3) | No |
| application_steps | `NotRequired[list[str]]` | Procedure steps when `intent_type == "procedure"` (step 3) | No |
| municipality_variation_note | `NotRequired[str]` | Mandatory when cost/provider answer lacks a validated code (step 4) | No |
| wamnet_link | `NotRequired[str]` | WAM NET provider-lookup URL (step 4) | No |
| care_manager_referral_notice | `NotRequired[str]` | Non-suppressible referral notice (step 5) | No |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable `list[str]`)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)
- Every agent-specific field wrapped `NotRequired[...]` (CoE C8)

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, permissions, credential handle)
- [ ] ConnectionPolicy (retry/timeout strategy) — not needed (no external network call; KB is fixture-backed)
- [x] SecurityViolationError (S-1 trust gate, framework-enforced)
- [x] S-2: `_extra_security_gate_input()` — not needed beyond the default PII scan; S-1 already rejects
      care-recipient personal identifiers (My Number-shaped sequences) directly in `QueryNormalizeNode.execute()`
- [x] S-3: `_extra_security_gate_output()` — preservation-variant hooks on `MunicipalVariationNoteNode`
      (verifies the mandatory municipality-variation note is present in its own output when the
      cost/provider-without-code condition holds) and `ResponseValidateNode` (verifies the non-suppressible
      ケアマネジャー referral notice is present in its own output)
- [x] S-4: `emit_trace_event()` — at least one domain-specific event inside each `execute()`
      (`query_normalized`, `care_context_extracted`, `care_rules_retrieved`,
      `municipal_variation_note_applied`, `response_validated`, plus the GraphNode dispatch/completion
      events `care_rules_workflow_dispatched`/`care_rules_workflow_completed`)

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass → framework `@final` gate always runs automatically;
>   extend via `_extra_security_gate_input()` / `_extra_security_gate_output()` only
> - `GraphNode` / `RemoteAgentNode` → deliberate no-op (upstream or remote node's gate already applied);
>   `CareQaGraphNode` follows this — the inner subgraph's own nodes apply S-2/S-3 individually
> - Custom `BaseNode` subclass → must implement `_security_gate_input()` and
>   `_security_gate_output()` directly (`@abstractmethod` — omission raises `TypeError` at instantiation)

### Composition Pattern

- **Pattern**: GraphNode (subgraph) — `CareQaGraphNode` wraps `CareRulesWorkflowGraph`
- **Composition target**: inner `BaseGraph` at `src/graph/domain_workflow_graph.py`
- **Error propagation strategy**: `propagate` (fail fast — inner errors surface as `SubgraphError`)

## S-5 Rate Limit (peak-period control)

`ResponseValidateNode` accepts an injectable `rate_limiter` (constructor parameter,
`None` = pass-through no-op by default). Production wiring provisions a real
per-caller limiter ahead of the April 2026 介護報酬改定 peak-demand window
(docs/01_proposal.md §11 risk 2). Extension point, not a hard dependency for
Stage ③/④.

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | AgentBaseGraph | Fixed 5-step Q&A pipeline, no autonomous loop needed |
| Composition pattern | Flat 3-slot (Cat 1 style) | GraphNode + inner subgraph (Cat 2) | GraphNode + inner subgraph | Cat 2 requires outer backbone + `GraphNode` in `main` wrapping the domain workflow (per the framework's composition-pattern guidance) |
| Municipality-code validation | Live JIS registry lookup | Format check (6-digit JIS X 0402 shape) | Format check | No live registry dependency at Stage ③/④; documented extension point |
| KB retrieval | Real vector store | Fixture-backed deterministic lookup | Fixture-backed | No unreleased vector-store dependency; `CareRulesKBService.retrieve()` is the swap point for production wiring |
| care_level LLM normalization wiring | Config-injected client (graph-config time) | Fresh per-invocation client from caller-bound secrets | Fresh per-invocation | A node instance is constructed once and reused across invocations via the registry's LRU cache; a client built once from graph config would leak whichever caller's secrets first constructed it to every later caller. Building `AzureOpenAIClient` inside `execute()` from `ctx.secrets.require(...)` keeps it scoped to the current call |

### care_level LLM Normalization — Security &amp; Error Handling

`CareContextExtractNode._normalize_care_level()` wraps client construction and the
LLM call in one `try/except Exception: return None`. A missing secret, an Azure
OpenAI API error, or a reply outside the seven canonical care-level values all
degrade identically: the node keeps the caller's raw free-text `care_level`
value (the deterministic baseline this node already produced before the LLM
existed) — it never raises and never sets `status=error`. The LLM reply is
validated against `_VALID_CARE_LEVELS` before being accepted; an unvalidated
reply never reaches state. `AZURE_OPENAI_API_KEY`/`_ENDPOINT`/`_DEPLOYMENT` are
declared secrets but deliberately excluded from `config/agent.yaml`'s
`requires.secrets` (see the comment there) so a registry-mediated compile never
hard-fails when the Azure key isn't configured — the same precedent the
scaffold blueprint already uses for `ANTHROPIC_API_KEY`.
