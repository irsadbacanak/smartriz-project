from typing import Dict, List, Optional, TypedDict


class TRIZState(TypedDict, total=False):
    original_problem: str
    analysis: Optional[str]
    contradictions: List[str]
    selected_principles: List[str]
    final_solution: Optional[str]
    critic_feedback: Optional[str]
    iterations: int
    meta: Optional[Dict[str, object]]
