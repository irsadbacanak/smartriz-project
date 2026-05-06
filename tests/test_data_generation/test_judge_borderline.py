"""
Tests for the borderline (FAIL) routing in judge.py and judge_sweep in orchestrator.py.

Verifies:
  - JudgeClient.score() returns a FAIL verdict dict (not None) when the judge rejects.
  - JudgeClient.score() returns None only on API/parse errors.
  - judge_sweep routes PASS cases to judged.jsonl and FAIL cases to borderline.jsonl.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from smartriz.data_generation.pipeline.judge import JudgeClient
from smartriz.data_generation.pipeline.orchestrator import judge_sweep


def _run(coro):
    """Run a coroutine synchronously."""
    return asyncio.run(coro)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_cost_tracker():
    tracker = MagicMock()
    tracker.add = MagicMock(return_value=0.0)
    return tracker


def _pass_scores():
    return {
        "verdict": "PASS",
        "Q1": "YES", "Q2": "YES", "Q3": "YES",
        "Q4": "YES", "Q5": "YES", "Q6": "YES",
        "fail_reasons": [],
        "average": 10.0,
    }


def _fail_scores(reasons=None):
    return {
        "verdict": "FAIL",
        "Q1": "NO", "Q2": "YES", "Q3": "YES",
        "Q4": "YES", "Q5": "YES", "Q6": "YES",
        "fail_reasons": reasons or ["principles not canonical"],
        "average": 0.0,
    }


# ── JudgeClient.score unit tests ───────────────────────────────────────────────

class TestJudgeClientScoreRouting:
    """score() must return FAIL dict (not None) when the judge rejects.

    _call_api is responsible for processing the raw LLM response into the
    normalised verdict dict. score() is a thin wrapper that calls _call_api
    and routes the result. We mock _call_api to return already-processed dicts.
    """

    def test_pass_returns_pass_dict(self):
        cost_tracker = _make_cost_tracker()
        client = JudgeClient(cost_tracker)
        case = {"id": "TEST-001", "problem": "x", "reasoning_chain": "y", "solution": "z"}

        async def _run_test():
            # _call_api returns the already-processed PASS dict
            with patch.object(client, "_call_api", new=AsyncMock(return_value=_pass_scores())):
                return await client.score(case)

        result = _run(_run_test())
        assert result is not None
        assert result["verdict"] == "PASS"
        assert result["average"] == 10.0

    def test_fail_returns_fail_dict_not_none(self):
        cost_tracker = _make_cost_tracker()
        client = JudgeClient(cost_tracker)
        case = {"id": "TEST-002", "problem": "x", "reasoning_chain": "y", "solution": "z"}

        async def _run_test():
            # _call_api returns the already-processed FAIL dict
            with patch.object(
                client, "_call_api",
                new=AsyncMock(return_value=_fail_scores(["bad principle"]))
            ):
                return await client.score(case)

        result = _run(_run_test())
        assert result is not None, "FAIL must return a dict, not None"
        assert result["verdict"] == "FAIL"
        assert result["average"] == 0.0
        assert "bad principle" in result["fail_reasons"]

    def test_api_error_returns_none(self):
        """None is reserved for genuine API/parse failures, not judge rejections."""
        cost_tracker = _make_cost_tracker()
        client = JudgeClient(cost_tracker)
        case = {"id": "TEST-003", "problem": "x"}

        async def _run_test():
            # Both first call and retry return None → simulates parse/network error
            with patch.object(client, "_call_api", new=AsyncMock(return_value=None)):
                return await client.score(case)

        result = _run(_run_test())
        assert result is None

    def test_unknown_verdict_handled_in_call_api(self):
        """_call_api converts unknown verdict strings to FAIL dicts.

        This tests the _call_api processing path directly by feeding it a raw
        HTTP response with an unrecognised verdict value. The method must return
        a FAIL dict rather than propagating the unknown value.
        """
        cost_tracker = _make_cost_tracker()
        client = JudgeClient(cost_tracker)

        # Build a fake httpx response that carries an unknown verdict
        bogus_payload = {
            "choices": [{"message": {"content": '{"verdict": "MAYBE", "fail_reasons": []}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_http_resp = MagicMock()
        mock_http_resp.json.return_value = bogus_payload
        mock_http_resp.raise_for_status = MagicMock()

        async def _run_test():
            with patch.object(
                client._client, "post", new=AsyncMock(return_value=mock_http_resp)
            ):
                return await client._call_api("sys", "user")

        result = _run(_run_test())
        assert result is not None
        assert result["verdict"] == "FAIL"


# ── judge_sweep routing integration test ──────────────────────────────────────

class TestJudgeSweepRouting:
    """judge_sweep must write PASS to judged.jsonl and FAIL to borderline.jsonl."""

    def test_pass_written_to_judged_fail_to_borderline(self, tmp_path):
        raw_path = tmp_path / "raw.jsonl"
        judged_path = tmp_path / "judged.jsonl"
        borderline_path = tmp_path / "borderline.jsonl"

        cases = [
            {"id": "CASE-PASS-01", "problem": "p", "meta": {}},
            {"id": "CASE-FAIL-01", "problem": "q", "meta": {}},
            {"id": "CASE-PASS-02", "problem": "r", "meta": {}},
        ]
        with open(raw_path, "w") as f:
            for c in cases:
                f.write(json.dumps(c) + "\n")

        # score() behaviour: PASS/FAIL/PASS
        score_returns = [_pass_scores(), _fail_scores(), _pass_scores()]
        call_idx = [0]

        async def mock_score(case):
            result = score_returns[call_idx[0]]
            call_idx[0] += 1
            return result

        mock_judge = MagicMock()
        mock_judge.score = mock_score

        pass_count, borderline_count = _run(judge_sweep(
            mock_judge,
            in_path=raw_path,
            out_path=judged_path,
            borderline_path=borderline_path,
        ))

        assert pass_count == 2
        assert borderline_count == 1

        judged_ids = [
            json.loads(line)["id"]
            for line in judged_path.read_text().splitlines()
            if line.strip()
        ]
        borderline_ids = [
            json.loads(line)["id"]
            for line in borderline_path.read_text().splitlines()
            if line.strip()
        ]

        assert sorted(judged_ids) == ["CASE-PASS-01", "CASE-PASS-02"]
        assert borderline_ids == ["CASE-FAIL-01"]

    def test_api_error_dropped_entirely(self, tmp_path):
        """Cases where score() returns None must not appear in either file."""
        raw_path = tmp_path / "raw.jsonl"
        judged_path = tmp_path / "judged.jsonl"
        borderline_path = tmp_path / "borderline.jsonl"

        with open(raw_path, "w") as f:
            f.write(json.dumps({"id": "ERR-01", "meta": {}}) + "\n")

        async def mock_score(case):
            return None

        mock_judge = MagicMock()
        mock_judge.score = mock_score

        pass_count, borderline_count = _run(judge_sweep(
            mock_judge, in_path=raw_path, out_path=judged_path, borderline_path=borderline_path
        ))

        assert pass_count == 0
        assert borderline_count == 0
        assert not judged_path.exists() or judged_path.read_text().strip() == ""
        assert not borderline_path.exists() or borderline_path.read_text().strip() == ""

    def test_already_processed_skipped(self, tmp_path):
        """Cases already in judged.jsonl or borderline.jsonl are not re-processed."""
        raw_path = tmp_path / "raw.jsonl"
        judged_path = tmp_path / "judged.jsonl"
        borderline_path = tmp_path / "borderline.jsonl"

        case = {"id": "DUP-01", "meta": {}}
        with open(raw_path, "w") as f:
            f.write(json.dumps(case) + "\n")

        # Pre-populate judged — simulate already processed
        with open(judged_path, "w") as f:
            f.write(json.dumps({**case, "meta": {"judge_scores": _pass_scores()}}) + "\n")

        score_called = [False]

        async def mock_score(case):
            score_called[0] = True
            return _pass_scores()

        mock_judge = MagicMock()
        mock_judge.score = mock_score

        _run(judge_sweep(
            mock_judge, in_path=raw_path, out_path=judged_path, borderline_path=borderline_path
        ))

        assert not score_called[0], "score() must not be called for already-processed case"
