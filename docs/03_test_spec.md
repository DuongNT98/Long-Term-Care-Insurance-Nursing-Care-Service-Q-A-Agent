# Test Specification

## Test Strategy
- Coverage target: all business-logic paths (unit + integration); hard % threshold enforced by CI gate
- Test types: Unit / Integration / Proof-of-Boundary

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict | Type check pass, no Pydantic/dataclass | PASS |
| TC-02 | Fail-closed validation on invalid input | Empty/invalid input → ERROR, no raise | PASS |
| TC-03 | No JWT/Credential in State | CI `gate-credential-scan`: 0 violations (S-5 enforcement moved to CI) | PASS |
| TC-04 | InvocationContext via configurable only | Direct access raises error | PASS |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `node_start` / `node_complete` / `node_error` absent from `execute()` body | 0 duplicates |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden (`@final` enforced by framework) | 0 overrides |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden (`@final` enforced by framework) | 0 overrides |
| TC-08 | `required_trust_level` enforced | Insufficient trust → refused | PASS |
| TC-09 | S-2: `_extra_security_gate_input()` non-trivial when domain checks needed | N/A for this template — S-1 rejects care-recipient identifiers directly in `QueryNormalizeNode.execute()`; default PII scan sufficient | N/A |
| TC-10 | S-3: `_extra_security_gate_output()` non-trivial when domain checks needed | Preservation-variant hooks on `MunicipalVariationNoteNode` + `ResponseValidateNode` verify their own non-suppressible output fields | PASS |
| TC-11 | S-4: at least one domain `emit_trace_event()` inside each `execute()` | Domain event emitted on every invocation path (all 5 nodes + GraphNode dispatch/completion) | ≥1 per node |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures | PASS |
| PB-2 | State serialization | Post-invoke State is primitives only | No Pydantic/dataclass | PASS |
| PB-3 | Level 2 → External service | N/A — KB retrieval is fixture-backed (`CareRulesKBService`), no live external service in this pass; extension point documented in docs/02_design.md | N/A |
| PB-4 | Import isolation | No Level 0 imports | AST scan: 0 violations | PASS |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | Inspection pass | PASS |
| PB-6 | Invoke execution order | `__call__()`: S-1 trust gate → S-4 `node_start` → S-2 `_security_gate_input` → `execute()` → S-3 `_security_gate_output` → S-4 `node_complete` | Order verified for every `src/nodes/` class (CI wheel gate of record) | PASS on CI |
| PB-7 | HITL interrupt propagation | N/A — `hitl.enabled` not set; stub auto-skips (`tests/proof_of_boundary/test_pb7_hitl_interrupt_propagation.py`) | N/A | SKIP (by design) |

## Business Logic Tests

| TC-ID | Test | Input | Expected Result | Result |
|-------|------|-------|----------------|--------|
| BL-01 | Eligibility question, no municipality code | "What are the eligibility rules for 要介護2?" | `care_service_guidance` + `applicable_law_ref` + `care_manager_referral_notice` present; no municipality-variation note (intent is not cost/provider) | PASS |
| BL-02 | Cost question without a municipality code | "How much does the day service cost?" | `municipality_variation_note` mandatory (non-empty) + `wamnet_link` present + `care_manager_referral_notice` present | PASS |
| BL-03 | Cost question with a valid municipality code | care_level/municipality_code supplied via `input_context` | No municipality-variation note (code validated) | PASS |
| BL-04 | Query containing a personal-identifier-shaped number | "My number is 123456789012, ..." | Rejected at `QueryNormalizeNode` (S-1) — end-to-end `status` is `error`/`cancelled` | PASS |
| BL-05 | Empty query | "" | `status` is `error`/`cancelled`, no raise | PASS |
| BL-06 | Free-text care_level, LLM available and normalizes to a canonical value | care_level="level two nursing care" (`llm=FakeLLM`) | `care_level` = the LLM's canonical reply | PASS |
| BL-07 | Free-text care_level, LLM reply outside the canonical set | care_level="level two nursing care" (`llm=FakeLLM` returns garbage) | `care_level` stays the raw free-text value (unvalidated reply rejected) | PASS |
| BL-08 | Free-text care_level, LLM raises | care_level="level two nursing care" (`llm=FakeLLM` raises) | `care_level` stays the raw free-text value; no raise, `status=success` | PASS |
| BL-09 | Free-text care_level, no `llm=` injected and no secrets bound | care_level="level two nursing care" (no `llm=`) | `care_level` stays the raw free-text value — the real production shape in any environment without a configured Azure key | PASS |
| BL-10 | Valid/absent care_level never calls the LLM | care_level="要介護1" or unset, `llm=` an object that raises `AssertionError` if called | LLM never invoked; `status=success` | PASS |

## Test Execution Summary
- Execution date: 2026-07-12 (LLM normalization cases BL-06..BL-10 added 2026-09-18 alongside the Azure OpenAI wiring)
- Total tests: unit (5 node test files + framework compliance) + 4 integration + 3 proof-of-boundary
- Pass: all except PB-7 (skip by design, `hitl.enabled` not set)
- Coverage: all business-logic paths covered (unit success + error/edge per node; ≥1 full-graph integration per intent branch); no real Azure OpenAI network call anywhere in the suite — BL-06..BL-09 use a test-double `FakeLLM`

Local note: `tests/proof_of_boundary/test_pb_invoke_order.py` (PB-6) and
`tests/unit/test_framework_compliance.py` TC-06/07 `@final` assertions may show
as skipped/failed on a stale local framework mirror that lacks
`emit_trace_event`/`@final` enforcement — this is an expected local
environment gap, not a test failure. CI wheel (`agenticstar-agentcore==1.0.0`)
is the gate of record and runs these assertions in full.
