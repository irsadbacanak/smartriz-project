from langgraph.graph import END, StateGraph

from agents.state import TRIZState


def problem_analyst(state: TRIZState):
    print("Agent: Analyzing Problem...")
    return {"analysis": "Initial problem analysis completed."}


def contradiction_detector(state: TRIZState):
    print("Agent: Detecting Contradictions...")
    return {"contradictions": ["Weight vs. Strength"]}


def react_solver(state: TRIZState):
    print("Agent: Generating Solution...")
    return {"final_solution": "Proposed TRIZ solution based on principles."}


def reflexion_critic(state: TRIZState):
    print("Agent: Evaluating Solution...")
    return {"critic_feedback": "Approved", "iterations": state.get("iterations", 0) + 1}


workflow = StateGraph(TRIZState)

workflow.add_node("analyst", problem_analyst)
workflow.add_node("detector", contradiction_detector)
workflow.add_node("solver", react_solver)
workflow.add_node("critic", reflexion_critic)

workflow.set_entry_point("analyst")
workflow.add_edge("analyst", "detector")
workflow.add_edge("detector", "solver")
workflow.add_edge("solver", "critic")
workflow.add_edge("critic", END)

triz_app = workflow.compile()
