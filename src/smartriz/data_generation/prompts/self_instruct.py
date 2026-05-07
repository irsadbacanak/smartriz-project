"""
Self-Instruct prompt template.

Given one seed case, generates 5 NEW TRIZ case studies that:
  - Use the SAME domain as the seed
  - Identify INDEPENDENT contradictions (NOT the parent's)
  - Select principles from the contradiction matrix for each NEW contradiction
  - Vary problem-statement style across the 5 outputs
  - Vary reasoning chain structure (length, format, depth)
"""
from __future__ import annotations


def build_prompt(
    seed: dict,
    temperature_hint: float = 0.7,
    used_contradictions: list[str] | None = None,
    used_solutions: list[str] | None = None,
) -> tuple[str, str]:
    """Return (system, user) prompt for self-instruct generation."""
    from smartriz.data_generation.quality.triz_kb import principles_reference_block
    canonical_list = principles_reference_block()

    system = (
        "You are a TRIZ expert and senior ML dataset engineer.\n"
        "Generate exactly 5 NEW TRIZ case studies in the SAME engineering domain as the seed.\n\n"
        "CRITICAL — DO NOT COPY THE SEED'S CONTRADICTION OR PRINCIPLES:\n"
        "Each case must identify its OWN independent engineering problem in the same domain.\n"
        "Independently select the contradiction parameters and look up the matrix.\n\n"
        "CRITICAL — PRINCIPLE NAMES:\n"
        "You MUST select principles ONLY from this exact list:\n"
        f"{canonical_list}\n\n"
        "Do NOT invent principle names or numbers. Do NOT use any number above #40.\n"
        "Cite each principle as: '#<number> <exact name from list>'\n\n"
        "REASONING CHAIN VARIETY (mandatory — rotate across the 5 outputs):\n"
        "  Case 1: numbered steps, simple (4-6 steps)\n"
        "  Case 2: paragraph narrative, medium depth\n"
        "  Case 3: Q&A dialogue format — pose counterfactuals\n"
        "  Case 4: numbered steps with cross-domain analogy, complex (10+ steps)\n"
        "  Case 5: academic abstract style with trade-off acknowledgment\n\n"
        "PROBLEM STATEMENT STYLE — also rotate:\n"
        "  (1) formal engineering specification\n"
        "  (2) casual narrative\n"
        "  (3) quantitative bug-report with numbers\n"
        "  (4) customer complaint\n"
        "  (5) academic abstract\n\n"
        "RESPOND ONLY WITH VALID JSON matching the schema exactly."
    )

    used_c_block = ""
    if used_contradictions:
        used_c_block = (
            "\nALREADY USED CONTRADICTIONS FOR THIS SEED (your 5 cases must NOT repeat these):\n"
            + "\n".join(f"  - {c}" for c in used_contradictions)
            + "\n"
        )

    used_s_block = ""
    if used_solutions:
        used_s_block = (
            "\nALREADY USED SOLUTION MECHANISMS (do NOT paraphrase these):\n"
            + "\n".join(f"  - {s}" for s in used_solutions)
            + "\n"
        )

    schema_block = '''{
  "variations": [
    {
      "id": "GEN-{SEED_ID}-SI-1",
      "source": "self_instruct_generated",
      "language": "en",
      "domain": "<same domain as seed>",
      "problem": "<NEW engineering problem in style 1 — DO NOT reference seed problem>",
      "contradiction_pair": {
        "improving_parameter": "<NEW parameter Name (#N) — NOT from seed>",
        "worsening_parameter": "<NEW parameter Name (#N) — NOT from seed>"
      },
      "inventive_principles": ["#<N> <exact canonical name>"],
      "reasoning_chain": "<varied structure per case — see style rules>",
      "solution": "<concrete solution derived from YOUR chosen principles>",
      "complexity": "simple|medium|complex"
    },
    ... (total 5 objects)
  ]
}'''

    import json
    user = f"""SEED CASE (domain reference only — do NOT copy its contradiction or principles):
{json.dumps(seed, ensure_ascii=False, indent=2)}
{used_c_block}{used_s_block}
OUTPUT SCHEMA:
{schema_block}

Rules:
- Each case must use a DIFFERENT contradiction_pair from every other case in this batch.
- Variation ids: replace {{SEED_ID}} with "{seed.get('id', 'UNKNOWN')}".
- complexity must be realistic for the problem (not all "simple").
- reasoning_chain style MUST vary across the 5 cases (see system prompt).
"""
    return system, user
