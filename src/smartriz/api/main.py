import json
import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from smartriz.agents.graph import stream_analysis_events, triz_app
from smartriz.agents.state import TRIZState

_MODEL_NAME = os.getenv("SMARTRIZ_LOCAL_MODEL", "qwen2.5:7b-instruct")

app = FastAPI(title="SmarTRIZ API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProblemRequest(BaseModel):
    problem: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/analyze")
def analyze_problem(request: ProblemRequest) -> TRIZState:
    if not request.problem.strip():
        raise HTTPException(status_code=400, detail="Problem description cannot be empty.")

    initial_state: TRIZState = {
        "original_problem": request.problem,
        "analysis": None,
        "contradictions": [],
        "selected_principles": [],
        "principle_applications": None,
        "final_solution": None,
        "critic_feedback": None,
        "iterations": 0,
    }

    try:
        t0 = time.perf_counter()
        result = triz_app.invoke(initial_state)
        duration = round(time.perf_counter() - t0, 1)
        result["meta"] = {**(result.get("meta") or {}), "duration_seconds": duration, "model": _MODEL_NAME}
        return result
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/api/stream")
def analyze_problem_stream(problem: str):
    if not problem.strip():
        raise HTTPException(status_code=400, detail="Problem description cannot be empty.")

    initial_state: TRIZState = {
        "original_problem": problem,
        "analysis": None,
        "contradictions": [],
        "selected_principles": [],
        "principle_applications": None,
        "final_solution": None,
        "critic_feedback": None,
        "iterations": 0,
    }

    def event_stream():
        try:
            t0 = time.perf_counter()
            final_state: TRIZState = initial_state
            for event in stream_analysis_events(initial_state):
                if event["event"] == "agent_done":
                    updates = event.get("updates") or {}
                    final_state = {**final_state, **updates}
                payload = json.dumps(event)
                yield f"event: {event['event']}\ndata: {payload}\n\n"

            duration = round(time.perf_counter() - t0, 1)
            final_state["meta"] = {
                **(final_state.get("meta") or {}),
                "duration_seconds": duration,
                "model": _MODEL_NAME,
            }
            complete_payload = json.dumps({"event": "complete", "result": final_state})
            yield f"event: complete\ndata: {complete_payload}\n\n"
        except Exception as error:
            error_payload = json.dumps({"event": "error", "message": str(error)})
            yield f"event: error\ndata: {error_payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
