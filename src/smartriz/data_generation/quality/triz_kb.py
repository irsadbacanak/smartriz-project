"""
Canonical TRIZ 40 Inventive Principles knowledge base.

Single source of truth for principle numbers, names, and accepted aliases.
Used by validate_principles() as a hard gate in the generation pipeline.
"""
from __future__ import annotations
import logging
import re

logger = logging.getLogger(__name__)

TRIZ_PRINCIPLES: dict[int, str] = {
    1: "Segmentation",
    2: "Taking Out",
    3: "Local Quality",
    4: "Asymmetry",
    5: "Merging",
    6: "Universality",
    7: "Nested Doll",
    8: "Anti-Weight",
    9: "Preliminary Anti-Action",
    10: "Preliminary Action",
    11: "Beforehand Cushioning",
    12: "Equipotentiality",
    13: "The Other Way Round",
    14: "Spheroidality - Curvature",
    15: "Dynamics",
    16: "Partial or Excessive Actions",
    17: "Another Dimension",
    18: "Mechanical Vibration",
    19: "Periodic Action",
    20: "Continuity of Useful Action",
    21: "Skipping",
    22: "Blessing in Disguise",
    23: "Feedback",
    24: "Intermediary",
    25: "Self-Service",
    26: "Copying",
    27: "Cheap Short-Living Objects",
    28: "Mechanics Substitution",
    29: "Pneumatics and Hydraulics",
    30: "Flexible Shells and Thin Films",
    31: "Porous Materials",
    32: "Color Changes",
    33: "Homogeneity",
    34: "Discarding and Recovering",
    35: "Parameter Changes",
    36: "Phase Transitions",
    37: "Thermal Expansion",
    38: "Strong Oxidants",
    39: "Inert Atmosphere",
    40: "Composite Materials",
}

# Accepted aliases: lowercase alias → canonical number
_ALIASES: dict[str, int | None] = {
    "dynamism": 15,
    "dynamics": 15,
    "inversion": 13,
    "the other way round": 13,
    "nested doll": 7,
    "matryoshka": 7,
    "taking out": 2,
    "extraction": 2,
    "separation": 2,
    "intermediary": 24,
    "intermediary/mediator": 24,
    "mediator": 24,
    "mechanics substitution": 28,
    "mechanics substitution/field interaction": 28,
    "composite materials": 40,
    "composite": 40,
    "discarding and recovering": 34,
    "discarding/recovering": 34,
    "phase transitions": 36,
    "phase transition": 36,
    "thermal expansion": 37,
    "spheroidality": 14,
    "spheroidality - curvature": 14,
    "curvature": 14,
    "color changes": 32,
    "colour changes": 32,
    "color change": 32,
    "blessing in disguise": 22,
    "convert harm to benefit": 22,
    "pneumatics and hydraulics": 29,
    "pneumatics/hydraulics": 29,
    "pneumatic/vacuum": None,  # explicitly invalid — no principle #42
    "cheap short-living objects": 27,
    "cheap short-lived objects": 27,
    "parameter changes": 35,
    "partial or excessive actions": 16,
    "partial or excess actions": 16,
    "flexible shells and thin films": 30,
    "flexible shells/thin films": 30,
    "preliminary action": 10,
    "pre-action": 10,
    "preliminary anti-action": 9,
    "beforehand cushioning": 11,
    "cushioning": 11,
    "equipotentiality": 12,
    "strong oxidants": 38,
    "strong oxidant": 38,
    "inert atmosphere": 39,
    "inert gas": 39,
    "porous materials": 31,
    "porous material": 31,
    "homogeneity": 33,
    "universality": 6,
    "merging": 5,
    "asymmetry": 4,
    "feedback": 23,
    "skipping": 21,
    "rushing through": 21,
    "continuity of useful action": 20,
    "periodic action": 19,
    "mechanical vibration": 18,
    "another dimension": 17,
    "transition to a new dimension": 17,
    "segmentation": 1,
    "local quality": 3,
    "anti-weight": 8,
    "anti-gravity": 8,
    "self-service": 25,
    "copying": 26,
}


_RE_PRINCIPLE = re.compile(r"#(\d+)\s+(.*)", re.IGNORECASE)


def validate_principles(principles: list[str]) -> dict:
    """
    Validate a list of principle strings against the canonical TRIZ_PRINCIPLES dict.

    Each string should be in the form "#N Name" (e.g. "#14 Spheroidality - Curvature").

    Returns:
        {
            "valid": bool,          # True only if ALL principles pass
            "normalized": list[str],# Canonical form for each passing principle
            "rejected": list[dict], # {"original": str, "reason": str} for failures
        }
    """
    if not principles:
        return {
            "valid": False,
            "normalized": [],
            "rejected": [{"original": "", "reason": "empty principles list"}],
        }

    normalized: list[str] = []
    rejected: list[dict] = []

    for raw in principles:
        raw_stripped = raw.strip()
        m = _RE_PRINCIPLE.match(raw_stripped)

        if not m:
            rejected.append({
                "original": raw_stripped,
                "reason": "missing #N prefix — expected format '#<number> <name>'",
            })
            logger.info("[validate_principles] reject %r — no #N prefix", raw_stripped)
            continue

        num = int(m.group(1))
        name_given = m.group(2).strip()

        if num < 1 or num > 40:
            rejected.append({
                "original": raw_stripped,
                "reason": f"principle #{num} does not exist — valid range is #1–#40",
            })
            logger.info("[validate_principles] reject %r — number %d out of range", raw_stripped, num)
            continue

        canonical_name = TRIZ_PRINCIPLES[num]
        name_lower = name_given.lower()

        # Check exact canonical match (case-insensitive)
        if name_lower == canonical_name.lower():
            normalized.append(f"#{num} {canonical_name}")
            continue

        # Check alias map
        if name_lower in _ALIASES:
            resolved = _ALIASES[name_lower]
            if resolved is None:
                # Explicitly invalid alias
                rejected.append({
                    "original": raw_stripped,
                    "reason": f"'{name_given}' is not a valid TRIZ principle name",
                })
                logger.info("[validate_principles] reject %r — explicit invalid alias", raw_stripped)
                continue
            if resolved != num:
                rejected.append({
                    "original": raw_stripped,
                    "reason": (
                        f"name '{name_given}' maps to #{resolved} ({TRIZ_PRINCIPLES[resolved]}), "
                        f"not #{num} ({canonical_name})"
                    ),
                })
                logger.info(
                    "[validate_principles] reject %r — name/number mismatch (alias resolves to %d)",
                    raw_stripped, resolved,
                )
                continue
            # Alias matches the number → normalize to canonical
            normalized.append(f"#{num} {canonical_name}")
            continue

        # Partial-match fallback: name starts with canonical or vice versa
        if (len(canonical_name) >= 8 and name_lower.startswith(canonical_name.lower()[:8])) or \
           (len(name_lower) >= 8 and canonical_name.lower().startswith(name_lower[:8])):
            normalized.append(f"#{num} {canonical_name}")
            logger.info("[validate_principles] fuzzy-accept %r → '#%d %s'", raw_stripped, num, canonical_name)
            continue

        # Hard reject
        rejected.append({
            "original": raw_stripped,
            "reason": f"#{num} is '{canonical_name}', not '{name_given}'",
        })
        logger.info("[validate_principles] reject %r — wrong name for #%d", raw_stripped, num)

    return {
        "valid": len(rejected) == 0,
        "normalized": normalized,
        "rejected": rejected,
    }


def principles_reference_block() -> str:
    """Return a formatted string listing all 40 principles for injection into prompts."""
    lines = [f"  #{n} {name}" for n, name in sorted(TRIZ_PRINCIPLES.items())]
    return "\n".join(lines)
