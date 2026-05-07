from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from smartriz.agents.graph import triz_app


if __name__ == "__main__":
    initial_state = {
        "original_problem": "A heavy bridge component must remain strong while reducing weight.",
        "analysis": None,
        "contradictions": [],
        "selected_principles": [],
        "final_solution": None,
        "critic_feedback": None,
        "iterations": 0,
    }

    print("=== LangGraph Dry Run ===")
    result = triz_app.invoke(initial_state)
    print("\n=== Final State ===")
    print(result)
