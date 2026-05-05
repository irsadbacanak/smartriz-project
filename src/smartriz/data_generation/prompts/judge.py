"""
LLM-as-a-Judge prompt — four-criterion rubric.

Returns a JSON object with four individual scores (0–10 each) and an average.
A single-number 0–10 score is explicitly forbidden.

Criteria:
  contradiction_validity   — are improving and worsening parameters genuinely opposing forces?
  principle_correctness    — do the principles plausibly resolve the contradiction?
  reasoning_coherence      — does the chain logically connect problem → parameters → matrix → principles → solution?
  solution_feasibility     — is the solution physically/engineering-realistic and buildable?
"""
from __future__ import annotations

_SCORE_SCHEMA = """{
  "contradiction_validity": <integer 0-10>,
  "principle_correctness": <integer 0-10>,
  "reasoning_coherence": <integer 0-10>,
  "solution_feasibility": <integer 0-10>
}"""

_CRITERION_DEFINITIONS = """SCORING CRITERIA (score each independently on a 0–10 integer scale):

1. contradiction_validity (0–10)
   10 = The improving and worsening parameters are in direct, unavoidable tension in this specific
        engineering context. Increasing one demonstrably forces the other to degrade.
   5  = There is a plausible but weak or indirect relationship between the two parameters.
   0  = The parameters are not genuinely contradictory in the described context, or one/both
        parameters are not from the 39 TRIZ parameters.

2. principle_correctness (0–10)
   10 = Each listed inventive principle directly and specifically resolves the stated contradiction.
        The principle number and name match the standard Altshuller 40 Principles.
   5  = Principles are broadly relevant to the domain but not the best fit for this contradiction.
   0  = Principles are hallucinated (non-existent numbers), misnamed, or completely irrelevant.

3. reasoning_coherence (0–10)
   10 = The reasoning chain explicitly: (a) states the concrete problem, (b) maps to TRIZ parameters
        with IDs, (c) references a matrix lookup, (d) interprets the selected principle(s) for the
        specific context, (e) derives the solution from the principle. Steps flow logically.
   5  = Reasoning chain covers most steps but skips the matrix lookup or parameter IDs, or the
        connection from principle to solution is hand-wavy.
   0  = No logical progression; reasoning is circular, contradictory, or missing entirely.

4. solution_feasibility (0–10)
   10 = The solution is physically plausible, could be prototyped or manufactured with known
        materials/processes, and directly resolves the stated contradiction.
   5  = Solution is conceptually sound but vague, or requires speculative technology.
   0  = Solution is physically impossible, contradicts the laws of thermodynamics/mechanics,
        or is too abstract to be actionable."""


def build_prompt(case: dict) -> tuple[str, str]:
    """Return (system, user) prompt for the four-criterion judge."""
    system = (
        "You are a TRIZ expert and quality-control judge evaluating AI-generated engineering "
        "problem-solution cases. "
        "Score the provided case on FOUR separate criteria, each on a 0–10 integer scale. "
        "Be strict: 10/10 means expert-level, publishable quality. "
        "Do NOT produce a single combined score. "
        "RESPOND ONLY WITH VALID JSON matching the schema exactly — no prose."
    )

    import json
    user = f"""CASE TO EVALUATE:
{json.dumps(case, ensure_ascii=False, indent=2)}

{_CRITERION_DEFINITIONS}

OUTPUT SCHEMA (respond with exactly this JSON — no other text):
{_SCORE_SCHEMA}

Important:
- All four fields are required integers in range [0, 10].
- Do NOT output an "average" field — the caller computes it.
- Do NOT add explanations outside the JSON object.
"""
    return system, user
