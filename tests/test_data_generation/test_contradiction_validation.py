"""
Tests for contradiction-copying validation (BUG 4 + BUG 5 fixes).

RED phase: these tests are written BEFORE implementation and must fail first.
"""
from __future__ import annotations
import json
import pytest


# ── FIX 1: evol_cross_domain payload must not expose contradiction_pair ─────

class TestCrossdomainPayload:
    """Parent payload sent to cross-domain generator must not contain contradiction_pair."""

    def _get_user_prompt(self, variation: dict) -> str:
        from smartriz.data_generation.prompts.evol_cross_domain import build_prompt
        _, user = build_prompt(variation)
        return user

    def test_cross_domain_user_prompt_has_no_contradiction_pair_key(self):
        """The JSON blob sent to LLM must not include a 'contradiction_pair' field."""
        variation = {
            "id": "GEN-AT-01-SI-01",
            "domain": "civil/environmental",
            "problem": "Some problem statement",
            "complexity": "simple",
            "contradiction_pair": {
                "improving_parameter": "Stability of object's composition (#13)",
                "worsening_parameter": "Loss of substance (#23)",
            },
            "inventive_principles": ["#24 Intermediary"],
            "solution": "Use intermediary layer",
        }
        user = self._get_user_prompt(variation)

        # Find the JSON blob passed to the LLM
        # It should NOT contain contradiction_pair as a key
        # Parse just the injected JSON dict from the prompt
        lines = user.split("\n")
        # Collect the JSON block between the PARENT CASE header and TARGET DOMAIN line
        in_block = False
        json_lines = []
        for line in lines:
            if line.startswith("PARENT CASE"):
                in_block = True
                continue
            if in_block and line.startswith("TARGET DOMAIN"):
                break
            if in_block:
                json_lines.append(line)
        json_str = "\n".join(json_lines).strip()
        parent_dict = json.loads(json_str)

        assert "contradiction_pair" not in parent_dict, (
            f"contradiction_pair must NOT be in parent payload, but found: "
            f"{parent_dict.get('contradiction_pair')}"
        )

    def test_cross_domain_user_prompt_still_has_domain_and_problem(self):
        """Removing contradiction_pair must not accidentally remove domain or problem."""
        variation = {
            "id": "GEN-AT-01-SI-01",
            "domain": "civil/environmental",
            "problem": "Riprap protection causes downstream scour",
            "complexity": "medium",
            "contradiction_pair": {
                "improving_parameter": "Stability (#13)",
                "worsening_parameter": "Loss (#23)",
            },
            "inventive_principles": ["#24 Intermediary"],
            "solution": "Use intermediary layer",
        }
        user = self._get_user_prompt(variation)

        # id, domain, problem must still be present
        assert "GEN-AT-01-SI-01" in user
        assert "civil/environmental" in user
        assert "Riprap protection" in user


# ── FIX 2: validate_no_contradiction_copying ─────────────────────────────────

class TestValidateNoContradictionCopying:
    """Hard-reject cases where SI/XDOM copies parent's contradiction pair."""

    def _validate(self, generated_case: dict, parent_seed: dict, method: str = "self_instruct"):
        from smartriz.data_generation.quality.triz_kb import validate_no_contradiction_copying
        return validate_no_contradiction_copying(generated_case, parent_seed, method)

    def test_identical_contradiction_pair_fails_for_si(self):
        parent = {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}}
        child  = {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}}
        is_valid, reason = self._validate(child, parent, method="self_instruct")
        assert not is_valid
        assert "identical" in reason.lower() or "same" in reason.lower() or "copied" in reason.lower()

    def test_identical_contradiction_pair_fails_for_xdom(self):
        parent = {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}}
        child  = {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}}
        is_valid, reason = self._validate(child, parent, method="evol_cross_domain")
        assert not is_valid

    def test_different_contradiction_pair_passes_for_si(self):
        parent = {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}}
        child  = {"contradiction_pair": {"improving_parameter": "C (#3)", "worsening_parameter": "B (#2)"}}
        is_valid, _ = self._validate(child, parent, method="self_instruct")
        assert is_valid

    def test_different_contradiction_pair_passes_for_xdom(self):
        parent = {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}}
        child  = {"contradiction_pair": {"improving_parameter": "X (#9)", "worsening_parameter": "Y (#7)"}}
        is_valid, _ = self._validate(child, parent, method="evol_cross_domain")
        assert is_valid

    def test_identical_contradiction_pair_allowed_for_deepening(self):
        """Deepening intentionally keeps the primary contradiction pair."""
        parent = {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}}
        child  = {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}}
        is_valid, _ = self._validate(child, parent, method="evol_deepening")
        assert is_valid

    def test_identical_contradiction_pair_allowed_for_constraint(self):
        """Constraint evolution may keep the same pair (constraint changes principles)."""
        parent = {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}}
        child  = {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}}
        is_valid, _ = self._validate(child, parent, method="evol_constraint")
        assert is_valid

    def test_missing_contradiction_pair_in_child_fails_gracefully(self):
        parent = {"contradiction_pair": {"improving_parameter": "A", "worsening_parameter": "B"}}
        child  = {}  # no contradiction_pair key
        is_valid, reason = self._validate(child, parent, method="self_instruct")
        assert not is_valid


# ── FIX 2: variation_history seeded with parent contradiction ─────────────────

class TestVariationHistoryInit:
    """run_round() must pre-seed variation_history with each seed's own contradiction."""

    def test_variation_history_preseeded_helper_produces_correct_entry(self):
        """The helper that builds the initial variation_history dict works correctly."""
        from smartriz.data_generation.pipeline.seeds import build_initial_variation_history
        seeds = [
            {
                "id": "AT-01",
                "contradiction_pair": {
                    "improving_parameter": "Stability of composition (#13)",
                    "worsening_parameter": "Loss of substance (#23)",
                },
                "solution": "Use intermediary layer to separate components",
            },
            {
                "id": "AT-02",
                "contradiction_pair": {
                    "improving_parameter": "Weight of moving object (#1)",
                    "worsening_parameter": "Force (#10)",
                },
                "solution": "Nested frame reduces weight while maintaining rigidity",
            },
        ]
        history = build_initial_variation_history(seeds)

        assert "AT-01" in history
        assert "AT-02" in history
        # Seed's own CP must be in used_contradictions from the start
        at01_used = history["AT-01"]
        assert "Stability of composition (#13)|Loss of substance (#23)" in at01_used
        at02_used = history["AT-02"]
        assert "Weight of moving object (#1)|Force (#10)" in at02_used


# ── Sweep-phase filter: contradiction_copy_sweep ──────────────────────────────

class TestContradictionCopySweep:
    """contradiction_copy_sweep() must filter copied-CP cases from matrix_validated.jsonl."""

    def test_sweep_removes_copied_cp_cases_for_si(self, tmp_path):
        """SI cases with same CP as parent seed must be removed by sweep."""
        from smartriz.data_generation.pipeline.sweeps import contradiction_copy_sweep
        import json

        seed_lookup = {
            "AT-01": {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}},
        }

        in_file = tmp_path / "in.jsonl"
        # Two SI cases: one copies CP, one doesn't
        cases = [
            {
                "id": "GEN-AT-01-SI-1",
                "contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"},
                "meta": {"parent_seed_id": "AT-01", "generation_method": "self_instruct"},
            },
            {
                "id": "GEN-AT-01-SI-2",
                "contradiction_pair": {"improving_parameter": "C (#3)", "worsening_parameter": "D (#4)"},
                "meta": {"parent_seed_id": "AT-01", "generation_method": "self_instruct"},
            },
        ]
        in_file.write_text("\n".join(json.dumps(c) for c in cases))

        passed = contradiction_copy_sweep(in_path=in_file, seed_lookup=seed_lookup)
        assert passed == 1

        remaining = [json.loads(l) for l in in_file.read_text().splitlines() if l.strip()]
        assert len(remaining) == 1
        assert remaining[0]["id"] == "GEN-AT-01-SI-2"

    def test_sweep_keeps_deepening_cases_with_same_cp(self, tmp_path):
        """evol_deepening cases are allowed to keep parent CP."""
        from smartriz.data_generation.pipeline.sweeps import contradiction_copy_sweep
        import json

        seed_lookup = {
            "AT-01": {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}},
        }

        in_file = tmp_path / "in.jsonl"
        cases = [
            {
                "id": "GEN-AT-01-SI-1-DEEP",
                "contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"},
                "meta": {"parent_seed_id": "AT-01", "generation_method": "evol_deepening"},
            },
        ]
        in_file.write_text("\n".join(json.dumps(c) for c in cases))

        passed = contradiction_copy_sweep(in_path=in_file, seed_lookup=seed_lookup)
        assert passed == 1

    def test_sweep_removes_xdom_with_copied_cp(self, tmp_path):
        """evol_cross_domain cases with same CP as parent must be dropped."""
        from smartriz.data_generation.pipeline.sweeps import contradiction_copy_sweep
        import json

        seed_lookup = {
            "AT-01": {"contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"}},
        }

        in_file = tmp_path / "in.jsonl"
        cases = [
            {
                "id": "GEN-AT-01-SI-1-XDOM",
                "contradiction_pair": {"improving_parameter": "A (#1)", "worsening_parameter": "B (#2)"},
                "meta": {"parent_seed_id": "AT-01", "generation_method": "evol_cross_domain"},
            },
        ]
        in_file.write_text("\n".join(json.dumps(c) for c in cases))

        passed = contradiction_copy_sweep(in_path=in_file, seed_lookup=seed_lookup)
        assert passed == 0
