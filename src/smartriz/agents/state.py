from typing import Any, Dict, List, Optional, TypedDict


class TRIZState(TypedDict, total=False):
    original_problem: str
    analysis: Optional[str]
    contradictions: List[str]
    contradiction_details: Optional[List[Dict[str, Any]]]
    selected_principles: List[str]
    principle_applications: Optional[Dict[str, str]]
    final_solution: Optional[str]
    critic_feedback: Optional[str]
    iterations: int
    meta: Optional[Dict[str, object]]
