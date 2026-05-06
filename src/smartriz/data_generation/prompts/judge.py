"""
LLM-as-a-Judge prompt — binary pass/fail with 5 YES/NO questions.

Any NO answer fails the example immediately. No partial credit.
A failed example is never added to the dataset.
"""
from __future__ import annotations
from smartriz.data_generation.quality.triz_kb import principles_reference_block

_CANONICAL_LIST = principles_reference_block()

_SCHEMA = """{
  "Q1_principles_canonical": "YES or NO",
  "Q2_reasoning_uses_all_principles": "YES or NO",
  "Q3_contradiction_domain_match": "YES or NO",
  "Q4_solution_not_forced_fit": "YES or NO",
  "Q5_reasoning_not_template": "YES or NO",
  "verdict": "PASS or FAIL",
  "fail_reasons": ["<reason if any question is NO — empty list if all YES>"]
}"""


def build_prompt(case: dict) -> tuple[str, str]:
    """Return (system, user) prompt for binary pass/fail judge."""
    system = (
        "You are a TRIZ expert and quality-control judge.\n"
        "Evaluate the provided TRIZ case study by answering 5 binary questions.\n"
        "ANY 'NO' answer means the case FAILS. No partial credit.\n"
        "Be strict — a principle that is close but wrong in name or number is a NO for Q1.\n"
        "RESPOND ONLY WITH VALID JSON matching the schema exactly — no prose.\n\n"
        "CANONICAL PRINCIPLE REFERENCE (40 principles):\n"
        f"{_CANONICAL_LIST}"
    )

    import json
    user = f"""CASE TO EVALUATE:
{json.dumps(case, ensure_ascii=False, indent=2)}

Answer each question YES or NO.

Q1. Are ALL listed inventive_principles using EXACT canonical names from the reference list above?
    (Wrong number, invented name, or number above 40 = NO)

Q2. Does the reasoning_chain ACTUALLY USE every principle in inventive_principles?
    (A principle listed but not mentioned or applied in reasoning = NO)

Q3. Are the contradiction parameters logically consistent with the problem domain?
    (e.g., an electronics problem applying #29 Pneumatics and Hydraulics with no fluid system = NO)

Q4. Is the solution domain-native — NOT a forced copy of a parent seed's solution pattern?
    (Generic re-application of the same principle in a new domain without new logic = NO)

Q5. Is the reasoning_chain non-formulaic?
    (The exact pattern "1)Problem 2)Parameters 3)Matrix 4)Apply" for a medium/complex case = NO)
    (Simple cases with 4-6 step numbered reasoning are acceptable.)

OUTPUT SCHEMA (respond with exactly this JSON — no other text):
{_SCHEMA}
"""
    return system, user
