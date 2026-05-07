"""
Evol-Instruct Direction B — Constraint Addition.

Takes a self-instruct variation and adds a real-world constraint that:
  - Changes which inventive principles are most applicable
  - Comes from: cost ceiling, ISO/military standard, recyclability mandate,
    mass production (≥1M units/year), or harsh environment (-40°C to 200°C,
    deep sea, radiation field, etc.)
"""
from __future__ import annotations

_CONSTRAINT_EXAMPLES = [
    "must comply with RoHS / REACH regulation (no hazardous materials)",
    "must be manufacturable at ≥1,000,000 units/year at <$2 per unit material cost",
    "must operate reliably from -40°C to +125°C (automotive grade)",
    "must survive 10,000 g shock per MIL-STD-810",
    "must be fully recyclable at end-of-life (EU Ecodesign Regulation 2024)",
    "must pass ISO 13485 medical device quality requirements",
    "must function under 200 bar hydrostatic pressure (subsea application)",
    "must be produced with zero VOC emissions (clean-room environment)",
    "must achieve TRL-6 within 18 months on a €500k budget",
    "must be sterilisable by gamma irradiation without degradation",
]


def build_prompt(variation: dict) -> tuple[str, str]:
    """Return (system, user) prompt for constraint-addition evolution."""
    from smartriz.data_generation.quality.triz_kb import principles_reference_block
    canonical_list = principles_reference_block()

    system = (
        "You are a TRIZ expert and product compliance engineer.\n"
        "You will evolve the provided TRIZ case by imposing a realistic real-world constraint "
        "(regulatory, manufacturing, economic, or environmental).\n"
        "The constraint must genuinely change which inventive principles are most applicable "
        "— not just restate the original problem.\n"
        "Rewrite the problem, update or extend the inventive_principles list, "
        "and produce a fresh reasoning_chain that explains why the original principles "
        "are affected and which new principles are selected.\n\n"
        "CRITICAL — PRINCIPLE NAMES:\n"
        "You MUST select principles ONLY from this exact list:\n"
        f"{canonical_list}\n\n"
        "Do NOT invent principle names. Do NOT exceed #40.\n"
        "RESPOND ONLY WITH VALID JSON matching the schema exactly."
    )

    import json, random
    constraint = random.choice(_CONSTRAINT_EXAMPLES)

    schema_block = """{
  "id": "<parent_id>-CONST",
  "source": "evol_constraint_generated",
  "language": "en",
  "domain": "<same domain>",
  "problem": "<enriched problem that explicitly states the constraint and how it conflicts with the original solution>",
  "constraint_applied": "<one-sentence description of the real-world constraint>",
  "contradiction_pair": {
    "improving_parameter": "<same or updated improving parameter — Name (#N)>",
    "worsening_parameter": "<same or updated worsening parameter — Name (#N)>"
  },
  "inventive_principles": ["<updated principle list — constraint may add or replace principles>"],
  "reasoning_chain": "<step-by-step TRIZ reasoning: how the constraint changes the parameter mapping or matrix lookup, and which principles are now most applicable>",
  "solution": "<concrete solution that satisfies both the original objective and the new constraint>",
  "complexity": "<same as parent or higher>"
}"""

    user = f"""PARENT CASE:
{json.dumps(variation, ensure_ascii=False, indent=2)}

CONSTRAINT TO APPLY: "{constraint}"

YOUR TASK:
1. Integrate the constraint into the problem statement so it creates a genuine engineering tension.
2. Determine whether the constraint changes the improving or worsening parameter (update if yes).
3. Perform a fresh matrix lookup with the updated/confirmed contradiction pair.
4. Select inventive principles that apply under the constraint (may differ from parent).
5. Write a detailed reasoning_chain explaining the constraint's effect on principle selection.
6. Design a concrete solution that satisfies both the original objective and the constraint.

OUTPUT SCHEMA (respond with exactly this structure — valid JSON only):
{schema_block}

Critical rules:
- constraint_applied must be a factual real-world standard or requirement.
- The inventive_principles list must differ from the parent's (at least one addition or replacement).
- reasoning_chain must explain WHY the constraint changes principle selection.
- Do NOT invent fictional regulations — use real standards (ISO, IEC, MIL-STD, EU directives, etc.).
"""
    return system, user
