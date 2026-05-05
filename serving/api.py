from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.graph import triz_app
from agents.state import TRIZState

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
        "final_solution": None,
        "critic_feedback": None,
        "iterations": 0,
    }

    try:
        return triz_app.invoke(initial_state)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
