"""AgentCore Platform v1.0 — HCR-C2-054 domain service.

Deterministic retrieval over the 介護保険 rules KB (namespace `kaigo_hoken_rules`):
介護保険法 + MHLW guidance + 区分支給限度基準額/介護報酬単価 tables + WAM NET.

This module is the extension point for a real vector-store-backed retriever
(docs/02_design.md): swap the fixture lookup in `retrieve()` for a call to the
production vector store client injected via the constructor, keeping the same
`RetrievalResult` shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field

KB_NAMESPACE = "kaigo_hoken_rules"

_APPLICATION_STEPS = [
    "1. Apply for a care-need certification (要介護認定) at your municipality's long-term care insurance desk.",
    "2. A certification investigator visits for an assessment interview.",
    "3. The municipality issues a certified care level (要支援1/2 or 要介護1-5).",
    "4. Work with a ケアマネジャー (care manager) to build a care plan (ケアプラン).",
    "5. Start using certified services within your care level's benefit limit.",
]

# Fixture KB content keyed by care-level bucket. A real deployment swaps this
# for a vector-store similarity_search() call against namespace kaigo_hoken_rules.
_GUIDANCE_BY_BUCKET = {
    "支援": (
        "要支援1/2 recipients are eligible for preventive long-term care services "
        "(介護予防サービス) under the Long-Term Care Insurance Act, within a monthly "
        "benefit ceiling (区分支給限度基準額) set for their level."
    ),
    "介護": (
        "要介護1-5 recipients are eligible for long-term care services (介護サービス) "
        "under the Long-Term Care Insurance Act, within a monthly benefit ceiling "
        "(区分支給限度基準額) that increases with care level; providers bill at the "
        "current 介護報酬単価 (care-fee unit price) table."
    ),
    None: (
        "Long-Term Care Insurance (介護保険) eligibility, cost, and service-type "
        "coverage depend on your certified care level (要支援1/2 or 要介護1-5). "
        "Apply for a care-need certification at your municipality to determine "
        "your specific benefit limit and coverage."
    ),
}

_LAW_REFS = [
    "介護保険法 (Long-Term Care Insurance Act)",
    "厚生労働省 介護保険サービスに係る介護給付費単位数等サービスコード表 (MHLW service code / unit-price table)",
]


@dataclass
class RetrievalResult:
    passages: list[str] = field(default_factory=list)
    kb_source_ref: list[str] = field(default_factory=list)
    applicable_law_ref: list[str] = field(default_factory=list)
    guidance_text: str = ""
    application_steps: list[str] = field(default_factory=list)


class CareRulesKBService:
    """Retrieval over the `kaigo_hoken_rules` KB namespace.

    Fixture-backed for now (docs/02_design.md documents the swap to a real
    vector-store client); the public `retrieve()` contract is stable.
    """

    namespace = KB_NAMESPACE

    def _bucket(self, care_level: str | None) -> str | None:
        if not care_level:
            return None
        if care_level.startswith("要支援"):
            return "支援"
        if care_level.startswith("要介護"):
            return "介護"
        return None

    def retrieve(self, care_level: str | None, intent_type: str, query_text: str) -> RetrievalResult:
        del query_text  # reserved for the real similarity_search() swap
        bucket = self._bucket(care_level)
        guidance = _GUIDANCE_BY_BUCKET.get(bucket, _GUIDANCE_BY_BUCKET[None])
        application_steps = list(_APPLICATION_STEPS) if intent_type == "procedure" else []
        return RetrievalResult(
            passages=[guidance],
            kb_source_ref=[f"{KB_NAMESPACE}:{bucket or 'general'}"],
            applicable_law_ref=list(_LAW_REFS),
            guidance_text=guidance,
            application_steps=application_steps,
        )
