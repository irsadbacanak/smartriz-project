"""
Evol-Instruct Direction A — Deepening.

Takes a self-instruct variation and deepens it by:
  - Adding a secondary contradiction or hidden constraint
  - Increasing complexity by one level (simple→medium, medium→complex;
    complex stays complex but gains a third contradiction)
  - Combining 2–3 inventive principles in the solution
"""
from __future__ import annotations


def build_prompt(variation: dict) -> tuple[str, str]:
    """Return (system, user) prompt for deepening evolution."""
    system = (
        "You are a TRIZ expert specializing in multi-contradiction problems. "
        "You will deepen the provided TRIZ case by adding a secondary contradiction "
        "or a previously hidden engineering constraint that emerges when the primary "
        "contradiction is resolved. "
        "The solution must use 2–3 inventive principles working together. "
        "Complexity increases by one level (simple→medium, medium→complex; "
        "complex stays complex but must involve three contradictions). "
        "RESPOND ONLY WITH VALID JSON matching the schema exactly."
    )

    current_complexity = variation.get("complexity", "simple")
    next_complexity = {"simple": "medium", "medium": "complex", "complex": "complex"}[current_complexity]

    schema_block = """{
  "id": "<parent_id>-DEEP",
  "source": "evol_deepening_generated",
  "language": "en",
  "domain": "<same domain>",
  "problem": "<enriched problem statement that reveals the secondary contradiction or hidden constraint>",
  "contradiction_pair": {
    "improving_parameter": "<primary improving parameter from parent — Name (#N)>",
    "worsening_parameter": "<primary worsening parameter from parent — Name (#N)>"
  },
  "secondary_contradiction": {
    "improving_parameter": "<new improving parameter — Name (#N)>",
    "worsening_parameter": "<new worsening parameter — Name (#N)>"
  },
  "inventive_principles": ["<2–3 principles, e.g. #X Name, #Y Name, #Z Name>"],
  "reasoning_chain": "<step-by-step TRIZ reasoning covering BOTH contradictions: each parameter mapping, matrix lookup, and how the combined principles resolve them>",
  "solution": "<concrete solution that addresses both contradictions using the combined principles>",
  "complexity": "<next complexity level>"
}"""

    import json
    user = f"""PARENT CASE:
{json.dumps(variation, ensure_ascii=False, indent=2)}

YOUR TASK:
1. Identify a secondary contradiction or hidden constraint in the parent case.
2. Rewrite the problem statement to make this deeper conflict explicit.
3. Map the secondary contradiction to the 39 parameters (provide parameter names and numbers).
4. Perform a matrix lookup for the secondary contradiction and select additional principles.
5. Design a solution that uses 2–3 principles in combination.
6. Write a detailed reasoning_chain covering both contradictions.
7. Set complexity to "{next_complexity}".

OUTPUT SCHEMA (respond with exactly this structure — valid JSON only):
{schema_block}

Critical rules:
- Keep the original contradiction_pair intact; add secondary_contradiction.
- inventive_principles list must contain 2 or 3 principles total.
- reasoning_chain must cite matrix cells for BOTH contradictions.
- Do NOT lower complexity.
"""
    return system, user
