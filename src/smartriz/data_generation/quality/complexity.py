"""
Structural complexity validator for TRIZ case studies.

Validates that the 'complexity' label claimed by the generator is supported
by measurable structural evidence in the case.

Rules
-----
complex
    At least ONE of:
    - secondary_contradiction field is present and non-empty
    - inventive_principles has ≥ 3 entries
    - reasoning_chain length ≥ 800 characters

simple
    ALL of:
    - inventive_principles has ≤ 2 entries
    - reasoning_chain length ≤ 500 characters
    (if either condition fails the case is demoted / rejected)

medium
    Everything else is accepted without additional constraints.
"""
from __future__ import annotations

_COMPLEX_MIN_PRINCIPLES = 3
_COMPLEX_MIN_REASONING = 800

_SIMPLE_MAX_PRINCIPLES = 2
_SIMPLE_MAX_REASONING = 500


def validate_complexity(case: dict) -> tuple[bool, str]:
    """Return (ok, reason).

    ok=True  → complexity label is structurally consistent; case may proceed.
    ok=False → mismatch detected; caller should drop or reclassify.
    """
    claimed = case.get("complexity", "").lower()
    principles = case.get("inventive_principles", [])
    reasoning = case.get("reasoning_chain", "")
    secondary = case.get("secondary_contradiction")

    n_principles = len(principles)
    n_reasoning = len(reasoning)

    if claimed == "complex":
        has_secondary = bool(
            isinstance(secondary, dict)
            and (secondary.get("improving_parameter") or secondary.get("worsening_parameter"))
        )
        if has_secondary or n_principles >= _COMPLEX_MIN_PRINCIPLES or n_reasoning >= _COMPLEX_MIN_REASONING:
            return True, ""
        return False, (
            f"labeled 'complex' but no secondary_contradiction, "
            f"only {n_principles} principle(s), and reasoning_chain is {n_reasoning} chars "
            f"(need secondary OR ≥{_COMPLEX_MIN_PRINCIPLES} principles OR ≥{_COMPLEX_MIN_REASONING} chars)"
        )

    if claimed == "simple":
        violations = []
        if n_principles > _SIMPLE_MAX_PRINCIPLES:
            violations.append(
                f"{n_principles} principles (max {_SIMPLE_MAX_PRINCIPLES} for 'simple')"
            )
        if n_reasoning > _SIMPLE_MAX_REASONING:
            violations.append(
                f"reasoning_chain is {n_reasoning} chars (max {_SIMPLE_MAX_REASONING} for 'simple')"
            )
        if violations:
            return False, "labeled 'simple' but: " + "; ".join(violations)
        return True, ""

    # medium — always accepted
    return True, ""
