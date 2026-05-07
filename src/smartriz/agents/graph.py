from langgraph.graph import END, StateGraph

from smartriz.agents.llm_client import chat_json
from smartriz.agents.prompts import (
    ANALYST_SYSTEM,
    ANALYST_USER,
    CRITIC_SYSTEM,
    CRITIC_USER,
    DETECTOR_SYSTEM,
    DETECTOR_USER,
    SOLVER_SYSTEM,
    SOLVER_USER,
)
from smartriz.agents.state import TRIZState


def problem_analyst(state: TRIZState) -> dict:
    print("Agent: Analyzing Problem...")
    result = chat_json(
        system=ANALYST_SYSTEM,
        user=ANALYST_USER.format(problem=state["original_problem"]),
        schema_hint='{"analysis": "...", "system_boundary": "...", "key_parameters": [...]}',
    )
    return {
        "analysis": result.get("analysis", ""),
        "meta": {
            "system_boundary": result.get("system_boundary", ""),
            "key_parameters": result.get("key_parameters", []),
        },
    }


def contradiction_detector(state: TRIZState) -> dict:
    print("Agent: Detecting Contradictions...")
    result = chat_json(
        system=DETECTOR_SYSTEM,
        user=DETECTOR_USER.format(
            problem=state["original_problem"],
            analysis=state.get("analysis", ""),
        ),
        schema_hint='{"contradictions": ["Improving X worsens Y", ...]}',
    )
    contradictions = result.get("contradictions", [])
    # Clamp to 1-3 items
    contradictions = contradictions[:3] if contradictions else ["Improving strength worsens weight"]
    return {"contradictions": contradictions}


def react_solver(state: TRIZState) -> dict:
    print("Agent: Generating Solution...")
    contradictions_text = "\n".join(f"- {c}" for c in state.get("contradictions", []))
    result = chat_json(
        system=SOLVER_SYSTEM,
        user=SOLVER_USER.format(
            problem=state["original_problem"],
            contradictions=contradictions_text,
        ),
        schema_hint='{"selected_principles": ["1: Segmentation", ...], "final_solution": "..."}',
    )
    return {
        "selected_principles": result.get("selected_principles", []),
        "final_solution": result.get("final_solution", ""),
    }


def reflexion_critic(state: TRIZState) -> dict:
    print("Agent: Evaluating Solution...")
    result = chat_json(
        system=CRITIC_SYSTEM,
        user=CRITIC_USER.format(
            problem=state["original_problem"],
            analysis=state.get("analysis", ""),
            contradictions=", ".join(state.get("contradictions", [])),
            selected_principles=", ".join(state.get("selected_principles", [])),
            final_solution=state.get("final_solution", ""),
        ),
        schema_hint='{"critic_feedback": "...", "verdict": "approved|revise"}',
    )
    return {
        "critic_feedback": result.get("critic_feedback", ""),
        "iterations": state.get("iterations", 0) + 1,
    }


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
