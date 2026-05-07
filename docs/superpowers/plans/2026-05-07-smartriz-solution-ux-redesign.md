# SmarTRIZ Solution Screen UX Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Solution screen so the model's real TRIZ output is presented clearly: hero card with contradiction chips, paragraphed solution text, principle cards with problem-specific "Applied here as:" context, a compact reference matrix, and a proper collapsible reasoning chain — with confidence indicators removed.

**Architecture:** Backend gains a `principle_applications` dict in the solver output and pipeline duration in `meta`; frontend replaces the monolithic `SolutionOutput` component with `SolutionHero` + `SolutionBody`, compacts `ContradictionMatrix` to a single intersection cell, converts `ReasoningChain` from `dangerouslySetInnerHTML` to structural JSX, and fixes the `PrincipleDetailPanel` cosmetic bug.

**Tech Stack:** Python 3 / LangGraph / FastAPI (backend); React 18 / CSS custom properties (frontend). No new npm packages.

---

## File Map

### Created
- `ui/src/components/SolutionHero.jsx` — 2-column hero card: contradiction chips + meta strip
- `ui/src/components/SolutionBody.jsx` — parsed solution text + principles grid + critic blockquote

### Modified
- `src/smartriz/agents/state.py` — add `principle_applications: Optional[Dict[str, str]]`
- `src/smartriz/agents/prompts.py` — extend `SOLVER_SYSTEM` schema; enforce English output
- `src/smartriz/agents/graph.py` — parse `principle_applications` in `react_solver`
- `src/smartriz/api/main.py` — measure pipeline duration; inject `meta.duration_seconds` + `meta.model`
- `ui/src/styles/tokens.css` — add `--surface-2`, `--space-8`, `--radius-lg`
- `ui/src/components/PrincipleCard.jsx` — add `application` prop + "Applied here as:" block
- `ui/src/screens/ContradictionMatrix.jsx` — replace 39×39 grid with single intersection cell + expandable full grid
- `ui/src/screens/ReasoningChain.jsx` — structural JSX replacing `dangerouslySetInnerHTML`
- `ui/src/screens/PrincipleDetailPanel.jsx` — hide "Cases" heading when `cases` is empty
- `ui/src/App.jsx` — new layout; wire `principleApplications`; remove `confidence` memo; remove `SolutionOutput`
- `ui/src/App.css` — add new layout classes; remove unused `.confidence-*` and `.recommend-pill`

### Deleted
- `ui/src/screens/SolutionOutput.jsx` — replaced by SolutionHero + SolutionBody

---

## Task 1: Backend — Add `principle_applications` to State

**Files:**
- Modify: `src/smartriz/agents/state.py`

- [ ] **Step 1: Add the field to TRIZState**

Open `src/smartriz/agents/state.py` (currently 14 lines). Add `principle_applications`:

```python
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
```

- [ ] **Step 2: Verify the import compiles**

```bash
cd /Users/sevketugurel/Desktop/LIFTUP/smartriz-project
python -c "from smartriz.agents.state import TRIZState; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/smartriz/agents/state.py
git commit -m "feat(backend): add principle_applications field to TRIZState"
```

---

## Task 2: Backend — Extend SOLVER_SYSTEM Prompt

**Files:**
- Modify: `src/smartriz/agents/prompts.py`

The current `SOLVER_SYSTEM` ends with a JSON schema that has two fields. We add `principle_applications` and enforce English output.

- [ ] **Step 1: Update the SOLVER_SYSTEM string**

Replace the `SOLVER_SYSTEM` constant (lines 58–78 of `src/smartriz/agents/prompts.py`) with:

```python
SOLVER_SYSTEM = """You are a TRIZ inventive principles expert. Given contradictions, select relevant TRIZ inventive principles and propose a concrete solution.

All output strings MUST be in English.

The 40 TRIZ principles include:
1: Segmentation, 2: Taking out, 3: Local quality, 4: Asymmetry, 5: Merging,
6: Universality, 7: Nested doll, 8: Anti-weight, 9: Preliminary anti-action, 10: Preliminary action,
11: Beforehand cushioning, 12: Equipotentiality, 13: The other way round, 14: Spheroidality,
15: Dynamics, 16: Partial or excessive actions, 17: Another dimension, 18: Mechanical vibration,
19: Periodic action, 20: Continuity of useful action, 21: Skipping, 22: Blessing in disguise,
23: Feedback, 24: Intermediary, 25: Self-service, 26: Copying, 27: Cheap short-living,
28: Mechanics substitution, 29: Pneumatics and hydraulics, 30: Flexible shells and thin films,
31: Porous materials, 32: Color changes, 33: Homogeneity, 34: Discarding and recovering,
35: Parameter changes, 36: Phase transitions, 37: Thermal expansion, 38: Strong oxidants,
39: Inert atmosphere, 40: Composite materials

Respond with a JSON object containing exactly these fields:
{
  "selected_principles": ["<number>: <name>", ...],
  "principle_applications": {
    "<principle_number_as_string>": "<1-2 sentences describing how this principle is applied to THIS specific problem>",
    ...
  },
  "final_solution": "<concrete 4-8 sentence solution proposal applying the selected principles>"
}

Select 2-4 principles most relevant to resolving the contradictions.
The principle_applications keys must be the string form of the principle number (e.g. "1", "8")."""
```

Also update `SOLVER_USER` to include the schema hint reference (it's passed separately in `graph.py`, this is fine as-is).

- [ ] **Step 2: Update the schema_hint in graph.py to match**

In `src/smartriz/agents/graph.py`, line 93, update the `schema_hint` argument of the `react_solver` `chat_json` call:

```python
schema_hint='{"selected_principles": ["1: Segmentation"], "principle_applications": {"1": "Applied as..."}, "final_solution": "..."}',
```

- [ ] **Step 3: Verify prompts import cleanly**

```bash
python -c "from smartriz.agents.prompts import SOLVER_SYSTEM; print(SOLVER_SYSTEM[:80])"
```

Expected: first 80 chars of the new SOLVER_SYSTEM string.

- [ ] **Step 4: Commit**

```bash
git add src/smartriz/agents/prompts.py src/smartriz/agents/graph.py
git commit -m "feat(backend): extend SOLVER_SYSTEM to output principle_applications; enforce English"
```

---

## Task 3: Backend — Parse `principle_applications` in react_solver

**Files:**
- Modify: `src/smartriz/agents/graph.py`

- [ ] **Step 1: Update the react_solver node to extract and validate the new field**

Replace the `react_solver` function (lines 83–97) with:

```python
def react_solver(state: TRIZState) -> dict:
    print("Agent: Generating Solution...")
    contradictions_text = "\n".join(f"- {c}" for c in state.get("contradictions", []))
    result = chat_json(
        system=SOLVER_SYSTEM,
        user=SOLVER_USER.format(
            problem=state["original_problem"],
            contradictions=contradictions_text,
        ),
        schema_hint='{"selected_principles": ["1: Segmentation"], "principle_applications": {"1": "Applied as..."}, "final_solution": "..."}',
    )
    raw_apps = result.get("principle_applications")
    if isinstance(raw_apps, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in raw_apps.items()
    ):
        principle_applications = raw_apps
    else:
        principle_applications = None

    return {
        "selected_principles": result.get("selected_principles", []),
        "principle_applications": principle_applications,
        "final_solution": result.get("final_solution", ""),
    }
```

- [ ] **Step 2: Run the graph test to confirm the new field appears**

```bash
cd /Users/sevketugurel/Desktop/LIFTUP/smartriz-project
python scripts/run_graph_test.py 2>&1 | tail -30
```

Expected: `principle_applications` is present in the final state printout as a dict with string keys and string values. Example:
```
'principle_applications': {'1': 'Split the component into ...', '14': 'Use spherical geometry ...'}
```

If the model returns `None` on first run (it needs the updated prompt), that is acceptable for the test — the frontend handles `null` gracefully. What must NOT happen: a Python exception.

- [ ] **Step 3: Commit**

```bash
git add src/smartriz/agents/graph.py
git commit -m "feat(backend): parse principle_applications from solver LLM output"
```

---

## Task 4: Backend — Measure Pipeline Duration in main.py

**Files:**
- Modify: `src/smartriz/api/main.py`

- [ ] **Step 1: Import time and MODEL; patch both endpoints**

Replace `src/smartriz/api/main.py` with:

```python
import json
import time
import os

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
```

- [ ] **Step 2: Verify the API starts without error**

```bash
cd /Users/sevketugurel/Desktop/LIFTUP/smartriz-project
python -c "from smartriz.api.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/smartriz/api/main.py
git commit -m "feat(backend): measure pipeline duration; expose meta.duration_seconds and meta.model in response"
```

---

## Task 5: Frontend — Add Missing CSS Tokens

**Files:**
- Modify: `ui/src/styles/tokens.css`

The spec references `--surface-2`, `--space-8`, and `--radius-lg` which don't exist yet.

- [ ] **Step 1: Add the three new tokens inside `:root`**

In `ui/src/styles/tokens.css`, add after the existing `--space-6: 24px;` line:

```css
  --space-8: 32px;
  --radius-lg: 12px;
  --surface-2: #f0efe9;
```

Also add the dark-mode overrides inside `[data-theme="dark"]`:

```css
  --surface-2: #2a2927;
```

- [ ] **Step 2: Verify the CSS variable is available (visual check)**

No automated test for CSS; just confirm the file saved correctly by reading it.

- [ ] **Step 3: Commit**

```bash
git add ui/src/styles/tokens.css
git commit -m "feat(ui): add --surface-2, --space-8, --radius-lg CSS tokens"
```

---

## Task 6: Frontend — Update PrincipleCard to Accept `application` Prop

**Files:**
- Modify: `ui/src/components/PrincipleCard.jsx`

- [ ] **Step 1: Extend the component**

Replace `ui/src/components/PrincipleCard.jsx` with:

```jsx
export default function PrincipleCard({ principle, onExpand, application }) {
  return (
    <button className="principle-card" onClick={() => onExpand(principle)} type="button">
      <div className="principle-id numeric">P{principle.id}</div>
      <div className="principle-name">{principle.name}</div>
      <p className="principle-description">{principle.description}</p>
      {application ? (
        <div className="principle-application">
          <span className="application-label">Applied here as:</span>
          <p>{application}</p>
        </div>
      ) : null}
      <span className="principle-expand">→ Detail</span>
    </button>
  )
}
```

- [ ] **Step 2: Add the CSS for the new block in `App.css`**

Append to `ui/src/App.css`:

```css
.principle-application {
  margin-top: var(--space-2);
  padding: var(--space-3);
  background: var(--surface-2);
  border-left: 3px solid var(--principle);
  border-radius: var(--radius-sm);
  text-align: left;
}

.application-label {
  display: block;
  font-size: 11px;
  color: var(--text-3);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: var(--space-1);
}

.principle-application p {
  font-size: 12px;
  color: var(--text-2);
  line-height: 1.5;
}
```

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/PrincipleCard.jsx ui/src/App.css
git commit -m "feat(ui): add application prop to PrincipleCard with Applied here as block"
```

---

## Task 7: Frontend — Fix PrincipleDetailPanel Cases Heading Bug

**Files:**
- Modify: `ui/src/screens/PrincipleDetailPanel.jsx`

Currently the "Cases from knowledge base" div renders even when `cases` is empty. Fix it.

- [ ] **Step 1: Conditionally render the heading**

Replace `ui/src/screens/PrincipleDetailPanel.jsx` with:

```jsx
import CaseCard from '../components/CaseCard'

export default function PrincipleDetailPanel({ principle, cases, onApply, onClose }) {
  if (!principle) return null

  const hasCases = cases && cases.length > 0

  return (
    <aside className="detail-panel">
      <div className="panel-header">
        <h3>
          <span className="numeric">P{principle.id}</span> {principle.name}
        </h3>
        <button className="text-button" onClick={onClose} type="button">
          Close
        </button>
      </div>

      <ol className="subprinciple-list">
        {principle.sub_principles?.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
      </ol>

      {hasCases ? (
        <>
          <div className="cases-title">Cases from knowledge base</div>
          <div className="cases-column">
            {cases.slice(0, 3).map((item) => (
              <CaseCard key={item.id} item={item} />
            ))}
          </div>
        </>
      ) : null}

      <button className="primary-button panel-button" type="button" onClick={() => onApply(principle)}>
        Apply this principle →
      </button>
    </aside>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/screens/PrincipleDetailPanel.jsx
git commit -m "fix(ui): hide Cases heading in PrincipleDetailPanel when cases list is empty"
```

---

## Task 8: Frontend — Refactor ReasoningChain to Structural JSX

**Files:**
- Modify: `ui/src/screens/ReasoningChain.jsx`

Removes `dangerouslySetInnerHTML` entirely. Uses native `<details>/<summary>` for collapse.

- [ ] **Step 1: Rewrite the component**

Replace `ui/src/screens/ReasoningChain.jsx` with:

```jsx
function ReasoningSections({ state }) {
  const sections = []

  if (state.analysis) {
    sections.push({
      title: '1. Problem Analysis',
      content: <p>{state.analysis}</p>,
    })
  }

  const contradictions = state.contradictions || []
  if (contradictions.length > 0) {
    sections.push({
      title: '2. Identified Contradictions',
      content: (
        <ul>
          {contradictions.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      ),
    })
  }

  const principles = state.selected_principles || []
  if (principles.length > 0) {
    sections.push({
      title: '3. Selected TRIZ Principles',
      content: (
        <ul>
          {principles.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      ),
    })
  }

  if (state.final_solution) {
    sections.push({
      title: '4. Proposed Solution',
      content: <p>{state.final_solution}</p>,
    })
  }

  if (state.critic_feedback) {
    sections.push({
      title: '5. Critic Feedback',
      content: <p>{state.critic_feedback}</p>,
    })
  }

  return (
    <>
      {sections.map((s) => (
        <section className="reasoning-section" key={s.title}>
          <h3>{s.title}</h3>
          {s.content}
        </section>
      ))}
    </>
  )
}

export default function ReasoningChain({ state }) {
  return (
    <details className="reasoning-screen">
      <summary className="text-button reasoning-toggle">See full reasoning chain</summary>
      <div className="reasoning-content">
        <ReasoningSections state={state} />
      </div>
    </details>
  )
}
```

- [ ] **Step 2: Add CSS for the new section structure in `App.css`**

Append to `ui/src/App.css`:

```css
.reasoning-screen summary {
  cursor: pointer;
  list-style: none;
  margin-bottom: var(--space-3);
}

.reasoning-screen summary::-webkit-details-marker {
  display: none;
}

.reasoning-section {
  margin-bottom: var(--space-4);
}

.reasoning-section h3 {
  font-size: 13px;
  color: var(--text-2);
  margin-bottom: var(--space-2);
}

.reasoning-section ul {
  padding-left: 18px;
  margin: 0;
  display: grid;
  gap: var(--space-1);
}

.reasoning-section p {
  color: var(--text-2);
  font-size: 13px;
  line-height: 1.7;
}
```

- [ ] **Step 3: Commit**

```bash
git add ui/src/screens/ReasoningChain.jsx ui/src/App.css
git commit -m "refactor(ui): replace dangerouslySetInnerHTML in ReasoningChain with structural JSX"
```

---

## Task 9: Frontend — Compact ContradictionMatrix to Single Intersection Cell

**Files:**
- Modify: `ui/src/screens/ContradictionMatrix.jsx`

The current component renders the full 39×39 grid inline, always visible. The redesign shows only the intersection cell with a button to expand the full grid.

- [ ] **Step 1: Rewrite ContradictionMatrix.jsx**

Replace `ui/src/screens/ContradictionMatrix.jsx` with:

```jsx
import { useState } from 'react'
import ParameterChip from '../components/ParameterChip'

export default function ContradictionMatrix({
  parameters,
  improvingId,
  worseningId,
  matrixMap,
}) {
  const [showFull, setShowFull] = useState(false)
  const key = `${improvingId}-${worseningId}`
  const highlightedIds = matrixMap[key] || []
  const improvingParam = parameters[improvingId - 1]
  const worseningParam = parameters[worseningId - 1]

  return (
    <details className="reference-matrix-details">
      <summary className="text-button">Reference: TRIZ-39 contradiction matrix</summary>

      <div className="reference-matrix-body">
        <div className="reference-matrix-cell">
          <div className="ref-cell-header">
            <ParameterChip label={`#${improvingId} ${improvingParam?.name || ''}`} trend="up" />
            <span className="chip-conflict">×</span>
            <ParameterChip label={`#${worseningId} ${worseningParam?.name || ''}`} trend="down" />
          </div>
          <div className="ref-cell-content">
            <span className="ref-cell-label">Model selected:</span>
            <span className="ref-cell-value">
              {highlightedIds.length > 0
                ? highlightedIds.map((id) => `P${id}`).join(' · ')
                : 'principles from model output above'}
            </span>
          </div>
          <div className="ref-cell-content">
            <span className="ref-cell-label">TRIZ-39 matrix suggests:</span>
            <span className="ref-cell-value">
              {highlightedIds.length > 0
                ? highlightedIds.map((id) => `P${id}`).join(', ')
                : '— (local model did not query matrix)'}
            </span>
          </div>
        </div>

        <button
          className="text-button ref-expand-btn"
          type="button"
          onClick={() => setShowFull((v) => !v)}
        >
          {showFull ? 'Collapse full matrix ↑' : 'Open full 39×39 matrix →'}
        </button>

        {showFull ? (
          <div className="matrix-wrapper">
            <table className="triz-matrix">
              <thead>
                <tr>
                  <th className="sticky-header sticky-corner">#</th>
                  {parameters.map((parameter) => (
                    <th
                      key={parameter.id}
                      className={`sticky-header ${parameter.id === worseningId ? 'worsening-col' : ''}`}
                    >
                      <span className="numeric">{parameter.id}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {parameters.map((row) => (
                  <tr key={row.id}>
                    <th className={`sticky-side ${row.id === improvingId ? 'improving-row' : ''}`}>
                      <span className="numeric">{row.id}</span>
                    </th>
                    {parameters.map((col) => {
                      const cellKey = `${row.id}-${col.id}`
                      const active = cellKey === key && highlightedIds.length > 0
                      return (
                        <td key={cellKey} className={active ? 'matrix-hit' : ''}>
                          {active ? highlightedIds.slice(0, 3).join(', ') : ''}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </details>
  )
}
```

Note: the `recommendedPrinciples` and `onExpandPrinciple` props are removed — they're no longer passed from `App.jsx` to this component (principles now live in `SolutionBody`).

- [ ] **Step 2: Add CSS in `App.css`**

Append to `ui/src/App.css`:

```css
.reference-matrix-details {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  padding: var(--space-3) var(--space-4);
}

.reference-matrix-details summary {
  cursor: pointer;
  list-style: none;
  font-size: 13px;
  color: var(--text-2);
}

.reference-matrix-details summary::-webkit-details-marker {
  display: none;
}

.reference-matrix-body {
  margin-top: var(--space-4);
  display: grid;
  gap: var(--space-3);
}

.reference-matrix-cell {
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  display: grid;
  gap: var(--space-2);
  min-height: 120px;
}

.ref-cell-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}

.ref-cell-content {
  display: flex;
  gap: var(--space-2);
  font-size: 13px;
  align-items: baseline;
}

.ref-cell-label {
  color: var(--text-3);
  min-width: 180px;
  flex-shrink: 0;
}

.ref-cell-value {
  color: var(--text-1);
  font-family: var(--font-mono);
  font-size: 12px;
}

.ref-expand-btn {
  justify-self: start;
  font-size: 12px;
  color: var(--principle);
  border-color: var(--principle);
}
```

- [ ] **Step 3: Commit**

```bash
git add ui/src/screens/ContradictionMatrix.jsx ui/src/App.css
git commit -m "refactor(ui): compact ContradictionMatrix to single intersection cell with expandable full grid"
```

---

## Task 10: Frontend — Create SolutionHero Component

**Files:**
- Create: `ui/src/components/SolutionHero.jsx`

- [ ] **Step 1: Create the component**

```jsx
import ParameterChip from './ParameterChip'

function formatDate(d) {
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function SolutionHero({ contradiction, problem, meta }) {
  const improving = contradiction?.improving_parameter || 'Improving parameter'
  const worsening = contradiction?.worsening_parameter || 'Worsening parameter'
  const model = meta?.model || 'local model'
  const duration = typeof meta?.duration_seconds === 'number'
    ? `${meta.duration_seconds.toFixed(1)}s`
    : '—'
  const generated = formatDate(new Date())

  return (
    <div className="solution-hero">
      <div className="hero-left">
        <p className="hero-label">Identified contradiction</p>
        <div className="hero-chips">
          <ParameterChip label={`↑ ${improving}`} trend="up" />
          <span className="chip-conflict">conflicts with</span>
          <ParameterChip label={`↓ ${worsening}`} trend="down" />
        </div>
        {problem ? <p className="hero-problem-summary">{problem}</p> : null}
      </div>
      <div className="hero-right">
        <div className="meta-strip">
          <span>Model: <span className="meta-mono">{model}</span></span>
          <span>Duration: <span className="meta-mono">{duration}</span></span>
          <span>Generated: <span className="meta-mono">{generated}</span></span>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add CSS for the hero in `App.css`**

Append to `ui/src/App.css`:

```css
.solution-hero {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-6);
  align-items: start;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-8) var(--space-6);
  margin-bottom: var(--space-6);
}

.hero-label {
  font-size: 12px;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--space-3);
}

.hero-chips {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.hero-problem-summary {
  margin-top: var(--space-3);
  font-size: 13px;
  color: var(--text-2);
  max-width: 560px;
  line-height: 1.6;
}

.hero-right {
  padding-top: var(--space-1);
}

.meta-strip {
  display: grid;
  gap: var(--space-2);
  font-size: 12px;
  color: var(--text-3);
  text-align: right;
}

.meta-mono {
  font-family: var(--font-mono);
  color: var(--text-2);
}
```

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/SolutionHero.jsx ui/src/App.css
git commit -m "feat(ui): add SolutionHero component with contradiction chips and meta strip"
```

---

## Task 11: Frontend — Create SolutionBody Component

**Files:**
- Create: `ui/src/components/SolutionBody.jsx`

- [ ] **Step 1: Create the component with parseSolution helper**

```jsx
import PrincipleCard from './PrincipleCard'

function parseSolution(text) {
  if (!text) return []
  const lines = text.split('\n')
  const result = []
  let paragraphLines = []

  const flush = () => {
    const content = paragraphLines.join(' ').trim()
    if (content) result.push({ type: 'p', content })
    paragraphLines = []
  }

  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed === '') {
      flush()
    } else if (/^[-*]\s/.test(trimmed)) {
      flush()
      result.push({ type: 'li', content: trimmed.replace(/^[-*]\s/, '') })
    } else if (/^\d+\.\s/.test(trimmed)) {
      flush()
      result.push({ type: 'li', content: trimmed.replace(/^\d+\.\s/, '') })
    } else {
      paragraphLines.push(trimmed)
    }
  }
  flush()
  return result
}

export default function SolutionBody({ finalSolution, principles, principleApplications, criticFeedback, onExpandPrinciple }) {
  const blocks = parseSolution(finalSolution)
  const listItems = blocks.filter((b) => b.type === 'li')
  const paragraphs = blocks.filter((b) => b.type === 'p')

  return (
    <div className="solution-body">
      <section className="solution-section-block">
        <h3 className="solution-section-title">Proposed solution</h3>
        <div className="solution-text">
          {paragraphs.map((b, i) => (
            <p key={i}>{b.content}</p>
          ))}
          {listItems.length > 0 ? (
            <ul className="solution-list">
              {listItems.map((b, i) => (
                <li key={i}>{b.content}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </section>

      {principles && principles.length > 0 ? (
        <section className="solution-section-block">
          <h3 className="solution-section-title">Principles applied</h3>
          <div className="principles-grid">
            {principles.map((p) => (
              <PrincipleCard
                key={p.id}
                principle={p}
                onExpand={onExpandPrinciple}
                application={principleApplications?.[String(p.id)] ?? null}
              />
            ))}
          </div>
        </section>
      ) : null}

      {criticFeedback ? (
        <section className="solution-section-block">
          <h3 className="solution-section-title">Critic insight</h3>
          <blockquote className="critic-blockquote">{criticFeedback}</blockquote>
        </section>
      ) : null}
    </div>
  )
}
```

- [ ] **Step 2: Add CSS for SolutionBody in `App.css`**

Append to `ui/src/App.css`:

```css
.solution-body {
  display: grid;
  gap: var(--space-6);
  max-width: 880px;
}

.solution-section-block {
  display: grid;
  gap: var(--space-3);
}

.solution-section-title {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-3);
  font-weight: 500;
}

.solution-text {
  display: grid;
  gap: 12px;
}

.solution-text p {
  line-height: 1.75;
  color: var(--text-1);
}

.solution-list {
  list-style: disc inside;
  padding-left: 4px;
  margin: 0;
  display: grid;
  gap: var(--space-2);
  color: var(--text-1);
}

.principles-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}

.critic-blockquote {
  border-left: 3px solid var(--text-3);
  margin: 0;
  padding: var(--space-3) var(--space-4);
  background: var(--surface-2);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.7;
  font-style: italic;
}
```

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/SolutionBody.jsx ui/src/App.css
git commit -m "feat(ui): add SolutionBody component with parsed solution text, principles grid, critic blockquote"
```

---

## Task 12: Frontend — Refactor App.jsx and Remove SolutionOutput

**Files:**
- Modify: `ui/src/App.jsx`
- Delete: `ui/src/screens/SolutionOutput.jsx`

This is the integration task. All new components get wired together.

- [ ] **Step 1: Rewrite App.jsx**

Replace `ui/src/App.jsx` with:

```jsx
import { useMemo, useState } from 'react'
import Breadcrumb from './components/Breadcrumb'
import SolutionBody from './components/SolutionBody'
import SolutionHero from './components/SolutionHero'
import { casesMock } from './data/casesMock'
import { matrixMock } from './data/matrixMock'
import { parameters } from './data/parameters'
import { principles } from './data/principles'
import { useTrizStream } from './hooks/useTrizStream'
import AgentPipeline from './screens/AgentPipeline'
import ContradictionMatrix from './screens/ContradictionMatrix'
import PrincipleDetailPanel from './screens/PrincipleDetailPanel'
import ProblemInput from './screens/ProblemInput'
import ReasoningChain from './screens/ReasoningChain'
import './App.css'

function resolvePair(result) {
  const detail = result?.contradiction_details?.[0]
  if (detail) {
    const imp = detail.improving_id
    const wors = detail.worsening_id
    if (Number.isInteger(imp) && Number.isInteger(wors) && imp >= 1 && imp <= 39 && wors >= 1 && wors <= 39) {
      return { improvingId: imp, worseningId: wors }
    }
  }
  return { improvingId: 27, worseningId: 14 }
}

function parsePrincipleEntry(entry) {
  const match = entry.match(/^(\d+):\s*(.+)$/)
  if (match) {
    return { id: parseInt(match[1], 10), name: match[2].trim() }
  }
  return null
}

export default function App() {
  const [problem, setProblem] = useState('')
  const [domain, setDomain] = useState('')
  const [expandedPrinciple, setExpandedPrinciple] = useState(null)
  const { status, result, error, agentStates, currentStep, start, reset } = useTrizStream()

  const pair = useMemo(() => resolvePair(result), [result])

  const recommendedPrinciples = useMemo(() => {
    const modelPrinciples = result?.selected_principles
    if (modelPrinciples && modelPrinciples.length > 0) {
      const cards = modelPrinciples.slice(0, 4).map((entry) => {
        const parsed = parsePrincipleEntry(entry)
        if (!parsed) return null
        const found = principles.find((p) => p.id === parsed.id)
        return found || { id: parsed.id, name: parsed.name, description: parsed.name }
      }).filter(Boolean)
      if (cards.length > 0) return cards
    }
    const matrixKey = `${pair.improvingId}-${pair.worseningId}`
    const ids = matrixMock[matrixKey] || [15, 35, 1]
    return principles.filter((item) => ids.includes(item.id))
  }, [result, pair])

  const domainCases = useMemo(() => {
    if (!domain) return []
    const selected = casesMock.filter((item) => item.domain === domain)
    return selected.length ? selected : casesMock
  }, [domain])

  const handleAnalyze = () => {
    if (!problem.trim()) return
    start(problem)
  }

  const handleRefine = () => {
    reset()
    setExpandedPrinciple(null)
  }

  const primaryContradiction = result?.contradiction_details?.[0] || null

  return (
    <div className="app-shell">
      {status !== 'idle' ? <Breadcrumb currentStep={currentStep} /> : null}

      {status === 'idle' || status === 'error' ? (
        <>
          <ProblemInput
            problem={problem}
            domain={domain}
            improvementParameter=""
            onProblemChange={setProblem}
            onDomainChange={setDomain}
            onImprovementParameterChange={() => {}}
            onAnalyze={handleAnalyze}
          />
          {error ? <p className="inline-error">{error}</p> : null}
        </>
      ) : null}

      {status === 'running' ? <AgentPipeline agentStates={agentStates} /> : null}

      {status === 'complete' ? (
        <main className="results-page">
          <SolutionHero
            contradiction={primaryContradiction}
            problem={problem}
            meta={result?.meta}
          />

          <SolutionBody
            finalSolution={result?.final_solution}
            principles={recommendedPrinciples}
            principleApplications={result?.principle_applications}
            criticFeedback={result?.critic_feedback}
            onExpandPrinciple={setExpandedPrinciple}
          />

          <ContradictionMatrix
            parameters={parameters}
            improvingId={pair.improvingId}
            worseningId={pair.worseningId}
            matrixMap={matrixMock}
          />

          <ReasoningChain state={result} />

          <div className="footer-actions">
            <button className="outline-button" type="button">
              Export as PDF
            </button>
            <button className="primary-button" type="button" onClick={handleRefine}>
              Refine problem →
            </button>
          </div>

          <PrincipleDetailPanel
            principle={expandedPrinciple}
            cases={domainCases}
            onApply={() => setExpandedPrinciple(null)}
            onClose={() => setExpandedPrinciple(null)}
          />
        </main>
      ) : null}
    </div>
  )
}
```

- [ ] **Step 2: Add the results-page layout CSS in `App.css`**

Append to `ui/src/App.css`:

```css
.results-page {
  display: grid;
  gap: var(--space-6);
  max-width: 1080px;
  margin: 0 auto;
}
```

- [ ] **Step 3: Delete SolutionOutput.jsx**

```bash
rm /Users/sevketugurel/Desktop/LIFTUP/smartriz-project/ui/src/screens/SolutionOutput.jsx
```

- [ ] **Step 4: Verify no broken imports**

```bash
cd /Users/sevketugurel/Desktop/LIFTUP/smartriz-project/ui
grep -r "SolutionOutput" src/
```

Expected: no output (no remaining references).

- [ ] **Step 5: Run lint**

```bash
cd /Users/sevketugurel/Desktop/LIFTUP/smartriz-project/ui
npm run lint
```

Expected: no errors. If ESLint reports unused imports, remove them.

- [ ] **Step 6: Commit**

```bash
git add ui/src/App.jsx ui/src/App.css
git rm ui/src/screens/SolutionOutput.jsx
git commit -m "feat(ui): refactor results layout to solution-first design; wire SolutionHero and SolutionBody"
```

---

## Task 13: Verify End-to-End

- [ ] **Step 1: Start backend**

```bash
cd /Users/sevketugurel/Desktop/LIFTUP/smartriz-project
pkill -f "uvicorn" 2>/dev/null; sleep 1
uvicorn smartriz.api.main:app --reload --port 8000 &
```

- [ ] **Step 2: Start frontend dev server**

```bash
cd /Users/sevketugurel/Desktop/LIFTUP/smartriz-project/ui
npm run dev &
```

- [ ] **Step 3: Run graph test to check principle_applications in final state**

```bash
cd /Users/sevketugurel/Desktop/LIFTUP/smartriz-project
python scripts/run_graph_test.py 2>&1 | grep -A 20 "Final State"
```

Expected: `principle_applications` key appears in output with a dict value (not `None`).

- [ ] **Step 4: Open browser and test the EV battery problem**

Navigate to `http://localhost:5173`. Enter:
> An EV battery pack heats up under fast charging but cooling adds weight.

Click Analyze. After processing completes, verify:
1. Hero card shows two contradiction chips (↑ improving / ↓ worsening)
2. Hero card right side shows model name, duration in seconds, date
3. "Proposed solution" section shows full text in paragraphs (not truncated at 4 bullets)
4. "Principles applied" grid shows 2–4 cards; each card with "Applied here as:" box (if `principle_applications` returned by model)
5. "Critic insight" blockquote appears below principles
6. "Reference: TRIZ-39 contradiction matrix" is collapsed; clicking expands the intersection cell; "Open full 39×39 matrix" button expands the full grid
7. "See full reasoning chain" is collapsed; expanding shows 5 sections with proper headings and ul/li/p structure (no raw HTML tags)
8. "Refine problem →" button resets to input screen
9. When clicking any principle card, PrincipleDetailPanel opens; "Cases from knowledge base" heading is absent when domain is not selected

- [ ] **Step 5: Run backend lint**

```bash
cd /Users/sevketugurel/Desktop/LIFTUP/smartriz-project
ruff check src/
```

Expected: no errors.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: verify e2e after solution UX redesign"
```

---

## Self-Review Against Spec

| Spec requirement | Task covering it |
|---|---|
| finalSolution `.split('.')` truncation removed | Task 11 (`parseSolution` in SolutionBody) |
| 39×39 matrix replaced with compact intersection cell | Task 9 |
| Principle cards show "Applied here as:" from backend | Tasks 2–3 (backend), Task 6 (frontend) |
| PrincipleDetailPanel "Cases" heading hidden when empty | Task 7 |
| ReasoningChain: structural JSX, no `dangerouslySetInnerHTML` | Task 8 |
| Confidence indicators removed | Task 12 (App.jsx rewrite removes confidence memo and prop) |
| SolutionHero with contradiction chips + meta strip | Task 10 |
| `principle_applications` added to state + prompts + parser | Tasks 1–3 |
| Pipeline duration in meta | Task 4 |
| `--surface-2`, `--space-8`, `--radius-lg` tokens | Task 5 |
| Mock files untouched | All tasks avoid mock data files |
| `application` prop gracefully absent → no "Applied here as:" | Task 6 (`application={... ?? null}` + conditional render) |
| `npm run lint` clean | Task 12 step 5 |
| `ruff check src/` clean | Task 13 step 5 |
| No new npm packages | No tasks add packages |
