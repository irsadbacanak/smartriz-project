"""
Evol-Instruct Direction C — Cross-Domain Transfer.

Keeps the same contradiction pair and inventive principles but transfers
the problem to a different engineering domain, finding an analogous situation
where the same principles apply.

Domain transfer pairs (bidirectional):
  aerospace ↔ biomedical
  automotive ↔ consumer electronics
  civil/environmental ↔ energy
  manufacturing ↔ robotics
  materials ↔ chemical
  ergonomics ↔ sports/biomedical
"""
from __future__ import annotations

_DOMAIN_TRANSFER_MAP: dict[str, list[str]] = {
    "aerospace": ["biomedical", "robotics"],
    "automotive": ["consumer-electronics", "energy"],
    "automotive/energy": ["consumer-electronics", "aerospace"],
    "biomedical": ["aerospace", "ergonomics"],
    "civil/environmental": ["energy", "chemical"],
    "consumer-electronics": ["automotive", "ergonomics"],
    "chemical": ["materials", "civil/environmental"],
    "energy": ["automotive", "civil/environmental"],
    "electronics": ["consumer-electronics", "robotics"],
    "ergonomics": ["biomedical", "sports/biomedical"],
    "manufacturing": ["robotics", "automotive"],
    "manufacturing/consumer-products": ["robotics", "consumer-electronics"],
    "manufacturing/materials": ["chemical", "biomedical"],
    "materials": ["chemical", "aerospace"],
    "robotics": ["manufacturing", "aerospace"],
    "sports/biomedical": ["ergonomics", "biomedical"],
}

_DEFAULT_TARGETS = ["biomedical", "consumer-electronics", "aerospace"]


def _pick_target_domain(source_domain: str) -> str:
    import random
    candidates = _DOMAIN_TRANSFER_MAP.get(source_domain, _DEFAULT_TARGETS)
    # Exclude the source itself
    candidates = [d for d in candidates if d.lower() != source_domain.lower()]
    return random.choice(candidates) if candidates else random.choice(_DEFAULT_TARGETS)


def build_prompt(variation: dict) -> tuple[str, str]:
    """Return (system, user) prompt for cross-domain transfer evolution."""
    from smartriz.data_generation.quality.triz_kb import principles_reference_block
    canonical_list = principles_reference_block()

    source_domain = variation.get("domain", "manufacturing")
    target_domain = _pick_target_domain(source_domain)

    system = (
        "You are a TRIZ expert specialising in domain-analogical transfer.\n"
        "You will create a NEW TRIZ case study in a different engineering domain.\n\n"
        "Use the PARENT CASE only for STRUCTURAL inspiration:\n"
        "  - The TYPE of contradiction (what kind of engineering trade-off it is)\n"
        "  - The DEPTH of reasoning expected\n"
        "DO NOT copy the parent's contradiction parameters, principle numbers, or solution.\n\n"
        "CRITICAL — PRINCIPLE NAMES:\n"
        "You MUST select principles ONLY from this exact list:\n"
        f"{canonical_list}\n\n"
        "Do NOT invent principle names. Do NOT use any number above #40.\n\n"
        "YOUR PROCESS:\n"
        "1. Identify a REAL engineering problem in the target domain.\n"
        "2. Extract ITS contradiction (improving vs worsening parameter).\n"
        "3. Look up the TRIZ matrix for THIS contradiction.\n"
        "4. Select principles that ACTUALLY apply in the target domain.\n"
        "5. Write domain-native reasoning and solution.\n\n"
        "RESPOND ONLY WITH VALID JSON matching the schema exactly."
    )

    import json
    schema_block = """{
  "id": "<parent_id>-XDOM",
  "source": "evol_cross_domain_generated",
  "language": "en",
  "domain": "<TARGET domain>",
  "problem": "<NEW problem in target domain — NOT derived from parent problem>",
  "source_domain": "<original domain for lineage tracing>",
  "target_domain": "<target domain>",
  "analogy_explanation": "<why the same TYPE of engineering trade-off appears in target domain>",
  "contradiction_pair": {
    "improving_parameter": "<parameter Name (#N) for TARGET domain problem>",
    "worsening_parameter": "<parameter Name (#N) for TARGET domain problem>"
  },
  "inventive_principles": ["#<N> <exact canonical name from list>"],
  "reasoning_chain": "<step-by-step TRIZ reasoning for TARGET domain: param mapping, matrix lookup, principle interpretation, solution>",
  "solution": "<concrete solution in target domain>",
  "complexity": "<realistic for the target problem>"
}"""

    # Show parent problem description ONLY — not its principles or solution
    parent_problem_only = {
        "id": variation.get("id"),
        "domain": variation.get("domain"),
        "problem": variation.get("problem"),
        "complexity": variation.get("complexity"),
        "contradiction_pair": variation.get("contradiction_pair"),
        # Deliberately omit inventive_principles and solution
    }

    user = f"""PARENT CASE (use for structural inspiration ONLY — do NOT copy principles or solution):
{json.dumps(parent_problem_only, ensure_ascii=False, indent=2)}

TARGET DOMAIN: {target_domain}

YOUR TASK:
1. Find an engineering system in "{target_domain}" facing a SIMILAR TYPE of trade-off.
2. Write a realistic problem statement entirely within "{target_domain}".
3. Extract the contradiction pair for THIS target-domain problem.
4. Look up the TRIZ matrix for the new contradiction pair.
5. Select principles from the matrix that apply to the target domain.
6. Write reasoning and solution native to "{target_domain}".

OUTPUT SCHEMA (valid JSON only):
{schema_block}

Critical rules:
- contradiction_pair must be derived from the TARGET problem, not copied from parent.
- inventive_principles must come from the matrix lookup for the new contradiction.
- The problem must be set entirely in "{target_domain}".
"""
    return system, user
