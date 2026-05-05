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
    source_domain = variation.get("domain", "manufacturing")
    target_domain = _pick_target_domain(source_domain)

    system = (
        "You are a TRIZ expert specialising in domain-analogical transfer. "
        "You will transfer the provided TRIZ case to a completely different engineering domain. "
        "The contradiction pair and inventive principles MUST remain identical. "
        "Find a genuinely analogous problem in the target domain where the same TRIZ logic applies. "
        "The new problem must be physically realistic and clearly belong to the target domain. "
        "RESPOND ONLY WITH VALID JSON matching the schema exactly."
    )

    import json
    schema_block = """{
  "id": "<parent_id>-XDOM",
  "source": "evol_cross_domain_generated",
  "language": "en",
  "domain": "<TARGET domain>",
  "problem": "<analogous engineering problem in the target domain — must NOT mention the source domain>",
  "source_domain": "<original domain for lineage tracing>",
  "target_domain": "<target domain>",
  "analogy_explanation": "<one sentence explaining why the same contradiction appears in the target domain>",
  "contradiction_pair": {
    "improving_parameter": "<EXACT copy from parent>",
    "worsening_parameter": "<EXACT copy from parent>"
  },
  "inventive_principles": ["<EXACT list from parent>"],
  "reasoning_chain": "<step-by-step TRIZ reasoning adapted to the target domain: same parameter mapping, same matrix cell, same principles — but new domain-specific interpretation>",
  "solution": "<concrete solution in the target domain using the same inventive principles>",
  "complexity": "<same as parent>"
}"""

    user = f"""PARENT CASE (source domain: {source_domain}):
{json.dumps(variation, ensure_ascii=False, indent=2)}

TARGET DOMAIN: {target_domain}

YOUR TASK:
1. Find an engineering system in "{target_domain}" that faces the SAME fundamental contradiction:
   improving "{variation.get('contradiction_pair', {}).get('improving_parameter', '?')}" 
   while "{variation.get('contradiction_pair', {}).get('worsening_parameter', '?')}" worsens.
2. Write a realistic problem statement entirely within the target domain.
3. Write a reasoning_chain that maps to the same parameters and matrix cell, 
   but interprets the principles through target-domain concepts.
4. Design a concrete solution in the target domain using the EXACT same inventive principles.

OUTPUT SCHEMA (respond with exactly this structure — valid JSON only):
{schema_block}

Critical rules:
- contradiction_pair MUST be copied EXACTLY (including parameter names and numbers).
- inventive_principles MUST be copied EXACTLY.
- The problem must be set entirely in "{target_domain}" — no cross-domain references.
- analogy_explanation must state concretely why the same contradiction appears.
- complexity = "{variation.get('complexity', 'simple')}" (unchanged).
"""
    return system, user
