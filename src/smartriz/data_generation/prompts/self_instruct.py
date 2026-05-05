"""
Self-Instruct prompt template.

Given one seed case, generates 5 variations that:
  - Preserve the contradiction_pair and inventive_principles exactly
  - Change the engineering context (different product/scale/scenario within the same domain)
  - Vary problem-statement style across the 5 outputs:
      1. formal specification
      2. casual narrative
      3. quantitative bug-report
      4. customer-complaint
      5. academic abstract
  - Keep the same complexity level
  - Include a freshly written reasoning_chain
"""
from __future__ import annotations

_EXAMPLE = """{
  "id": "GEN-EXAMPLE-001",
  "source": "self_instruct_generated",
  "language": "en",
  "domain": "manufacturing/materials",
  "problem": "A pneumatic sorting line for metal powder must push pellets quickly through ceramic nozzles. High velocity erodes the nozzle tip within 200 hours, forcing costly shutdowns.",
  "contradiction_pair": {
    "improving_parameter": "Speed (#9)",
    "worsening_parameter": "Stability of object's composition (#13)"
  },
  "inventive_principles": ["#28 Mechanics substitution"],
  "reasoning_chain": "1) High-speed metal pellets impact ceramic nozzle, eroding it. 2) Improving: throughput speed (#9). Worsening: stability of nozzle composition (#13). 3) Matrix (9,13) → {28,33,1,18}. 4) Pick #28: replace kinetic-impact interaction with a field-based one. 5) Embed a ring magnet at the nozzle exit to attract stray pellets and form a self-renewing metal lining. 6) The ceramic surface no longer contacts high-speed metal — erosion stops.",
  "solution": "A ring magnet at the nozzle exit attracts stray metal pellets, which form a continuously replenished sacrificial lining. The ceramic tip never contacts high-speed metal powder directly.",
  "complexity": "simple"
}"""


def build_prompt(seed: dict, temperature_hint: float = 0.7) -> str:
    """Return the system+user prompt for self-instruct generation."""
    system = (
        "You are a TRIZ expert and senior ML dataset engineer. "
        "Generate exactly 5 TRIZ problem-solution cases as variations of the provided seed. "
        "Each variation must use the SAME contradiction_pair and inventive_principles as the seed, "
        "but describe a DIFFERENT engineering scenario within the same domain. "
        "Write each variation in a different style: "
        "(1) formal engineering specification, "
        "(2) casual narrative, "
        "(3) quantitative bug-report with numbers, "
        "(4) customer complaint voice, "
        "(5) academic abstract voice. "
        "Keep the same complexity level. "
        "Write a fresh, detailed reasoning_chain for each variation. "
        "RESPOND ONLY WITH VALID JSON matching the schema exactly."
    )

    schema_block = '''{
  "variations": [
    {
      "id": "GEN-{SEED_ID}-SI-1",
      "source": "self_instruct_generated",
      "language": "en",
      "domain": "<same domain as seed>",
      "problem": "<new engineering problem in style 1 — formal spec>",
      "contradiction_pair": {
        "improving_parameter": "<EXACT copy from seed>",
        "worsening_parameter": "<EXACT copy from seed>"
      },
      "inventive_principles": ["<EXACT list from seed>"],
      "reasoning_chain": "<fresh step-by-step TRIZ reasoning: problem → parameters → matrix lookup → principle → solution>",
      "solution": "<concrete engineered solution>",
      "complexity": "<same as seed>"
    },
    ... (total 5 objects, styles 1-5)
  ]
}'''

    user = f"""SEED CASE:
{_format_seed(seed)}

IN-CONTEXT EXAMPLE (for schema reference):
{_EXAMPLE}

OUTPUT SCHEMA (respond with exactly this structure):
{schema_block}

Rules:
- Do NOT change contradiction_pair or inventive_principles.
- Do NOT copy the seed problem verbatim — create new scenarios.
- The domain field must remain the same as the seed.
- Each reasoning_chain must explicitly mention the improving and worsening parameter numbers and cite the matrix lookup.
- complexity = "{seed.get('complexity', 'simple')}" (unchanged).
- Variation ids: replace {{SEED_ID}} with "{seed.get('id', 'UNKNOWN')}".
"""
    return system, user


def _format_seed(seed: dict) -> str:
    import json
    return json.dumps(seed, ensure_ascii=False, indent=2)
