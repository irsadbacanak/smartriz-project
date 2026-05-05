from typing import List, Optional, TypedDict


class TRIZState(TypedDict):
    original_problem: str
    analysis: Optional[str]
    contradictions: List[str]
    selected_principles: List[str]
    final_solution: Optional[str]
    critic_feedback: Optional[str]
    iterations: int
