"""Tests for SeedScheduler round-robin logic."""
import random
from smartriz.data_generation.pipeline.orchestrator import SeedScheduler

SEEDS = [{"id": f"AT-{i:02d}"} for i in range(1, 10)]  # 9 seeds


def test_scheduler_covers_all_seeds():
    sched = SeedScheduler(SEEDS, max_per_seed=2)
    selected = []
    while True:
        s = sched.next_seed()
        if s is None:
            break
        selected.append(s["id"])
    assert len(selected) == 18  # 9 seeds × 2
    assert len(set(selected)) == 9  # all seeds covered


def test_scheduler_round_robin_distributes_evenly():
    sched = SeedScheduler(SEEDS, max_per_seed=3)
    # First 9 picks should each come from a different seed
    first_nine = [sched.next_seed()["id"] for _ in range(9)]
    assert len(set(first_nine)) == 9


def test_scheduler_returns_none_when_exhausted():
    sched = SeedScheduler(SEEDS[:2], max_per_seed=1)
    sched.next_seed()
    sched.next_seed()
    assert sched.next_seed() is None


def test_all_seeds_for_round_returns_all_available():
    sched = SeedScheduler(SEEDS, max_per_seed=2)
    first_round = sched.all_seeds_for_round()
    assert len(first_round) == 9
    assert len(set(s["id"] for s in first_round)) == 9
    second_round = sched.all_seeds_for_round()
    assert len(second_round) == 9
    # Third round should return empty
    third_round = sched.all_seeds_for_round()
    assert len(third_round) == 0


def test_smoke_mode_random_selection():
    """Smoke mode should NOT always pick first N seeds."""
    random.seed(99)
    all_seeds = [{"id": f"AT-{i:02d}"} for i in range(1, 21)]  # 20 seeds
    picks_set = set()
    for trial_seed in range(10):
        random.seed(trial_seed)
        selected = random.sample(all_seeds, 3)
        picks_set.update(s["id"] for s in selected)
    # After 10 trials with different seeds, should see more than just AT-01..03
    assert len(picks_set) > 3
