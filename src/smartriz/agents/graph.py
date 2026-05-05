from langgraph.graph import END, StateGraph

from smartriz.agents.state import TRIZState


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


AGENT_NAMES = {
    "analyst": "Problem Analyst",
    "detector": "Contradiction Detector",
    "solver": "ReAct Solver",
    "critic": "Reflexion Critic",
}


AGENT_LOG_LINES = {
    "analyst": "Parsed system boundary and failure context.",
    "detector": "Matched parameters: Reliability ↔ Strength of a moving object",
    "solver": "Mapped contradiction to candidate principles.",
    "critic": "Evaluated solution coherence and practical constraints.",
}


def stream_analysis_events(initial_state: TRIZState):
    for chunk in triz_app.stream(initial_state):
        for agent_id, updates in chunk.items():
            yield {
                "event": "agent_start",
                "agent": agent_id,
                "agent_name": AGENT_NAMES.get(agent_id, agent_id),
            }
            yield {
                "event": "agent_done",
                "agent": agent_id,
                "agent_name": AGENT_NAMES.get(agent_id, agent_id),
                "log_line": AGENT_LOG_LINES.get(agent_id, "Completed step."),
                "updates": updates,
            }
