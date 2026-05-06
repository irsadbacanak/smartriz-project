"""
LLM-as-a-Judge prompt — binary pass/fail with 6 YES/NO questions plus confidence.

Any NO answer fails the example immediately. No partial credit.
BORDERLINE FAIL cases (confidence="BORDERLINE") may be salvaged by the pipeline
with a downgraded complexity label rather than being discarded.
"""
from __future__ import annotations

import json

from smartriz.data_generation.quality.triz_kb import principles_reference_block

_CANONICAL_LIST = principles_reference_block()

# Only these fields are sent to the judge — strips meta, source, source_domain,
# target_domain, analogy_explanation and other generation artifacts that could
# bias Q4 ("is this a forced copy of a parent seed?").
_EVAL_KEYS = frozenset({
    "domain",
    "problem",
    "contradiction_pair",
    "secondary_contradiction",
    "inventive_principles",
    "reasoning_chain",
    "solution",
    "complexity",
})

_SCHEMA = """{
  "Q1_principles_canonical": "YES or NO",
  "Q2_reasoning_uses_all_principles": "YES or NO",
  "Q3_contradiction_domain_match": "YES or NO",
  "Q4_solution_not_forced_fit": "YES or NO",
  "Q5_reasoning_domain_specific": "YES or NO",
  "Q6_domain_terminology_accurate": "YES or NO",
  "verdict": "PASS or FAIL",
  "confidence": "HIGH or BORDERLINE",
  "fail_reasons": ["<reason if any question is NO — empty list if all YES>"]
}"""


def _build_eval_view(case: dict) -> dict:
    """Return only the evaluation-relevant fields of a case.

    Strips meta, source, source_domain, target_domain, analogy_explanation and
    other generation artifacts that could bias the judge (especially Q4).
    """
    return {k: v for k, v in case.items() if k in _EVAL_KEYS}


def build_prompt(case: dict) -> tuple[str, str]:
    """Return (system, user) prompt for binary pass/fail judge."""
    system = (
        "You are a TRIZ expert and quality-control judge.\n"
        "Evaluate the provided TRIZ case study by answering 6 binary questions.\n"
        "ANY 'NO' answer means the case FAILS. No partial credit.\n"
        "Be strict — a principle that is close but wrong in name or number is a NO for Q1.\n"
        "Set 'confidence' to BORDERLINE when any answer was a close call.\n"
        "RESPOND ONLY WITH VALID JSON matching the schema exactly — no prose.\n\n"
        "CANONICAL PRINCIPLE REFERENCE (40 principles):\n"
        f"{_CANONICAL_LIST}"
    )

    user = f"""CASE TO EVALUATE:
{json.dumps(_build_eval_view(case), ensure_ascii=False, indent=2)}

Answer each question YES or NO.

Q1. Are ALL listed inventive_principles using EXACT canonical names from the reference list above?
    (Wrong number, invented name, or number above 40 = NO)

Q2. Does the reasoning_chain ACTUALLY USE every principle in inventive_principles?
    (A principle listed but not mentioned or applied in reasoning = NO)

Q3. Are the contradiction parameters logically consistent with the problem domain?
    (e.g., an electronics problem applying #29 Pneumatics and Hydraulics with no fluid system = NO)

Q4. Is the solution domain-native — NOT a generic pattern copy?
    (A solution that could apply verbatim to any domain with minimal word substitution = NO)

Q5. Does the reasoning_chain demonstrate DOMAIN-SPECIFIC insight?
    (YES = reasoning explains WHY each principle fits THIS specific domain using domain-specific
     logic, materials, constraints, or mechanisms unique to the stated domain.
     NO = reasoning only states what a principle means in general then says "apply it here"
     with no domain-specific justification.
     Key test: if you replaced the domain name with a different domain and the reasoning still
     made perfect sense with minor word edits = NO.
     IMPORTANT: structured or numbered steps are perfectly acceptable — only shallow generic
     content is a NO, not the use of a numbered format.)

Q6. Are all material names, process terms, and physical properties in the solution/reasoning
    technically accurate for the stated domain?
    (e.g., claiming a ceramic/carbon composite has a "glass transition temperature",
     or citing a standard number that belongs to a different field = NO)

Set 'confidence' to BORDERLINE if any question was a close call (nearly YES but you said NO,
or nearly NO but you said YES, or there was genuine ambiguity). Set to HIGH when all answers
were clear-cut.

OUTPUT SCHEMA (respond with exactly this JSON — no other text):
{_SCHEMA}
"""
    return system, user
