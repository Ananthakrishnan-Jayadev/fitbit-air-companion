import datetime as dt

import numpy as np

from fitbit_app.analytics.correlations import tag_effects

START = dt.date(2026, 6, 1)


def _days(n: int) -> list[dt.date]:
    return [START + dt.timedelta(days=i) for i in range(n)]


def test_clear_negative_effect_is_detected() -> None:
    rng = np.random.default_rng(1)
    tags: dict[dt.date, list[str]] = {}
    outcomes: dict[dt.date, float | None] = {}
    for i, day in enumerate(_days(60)):
        drank = i % 3 == 0
        tags[day] = ["alcohol"] if drank else ["early_bedtime"]
        # The *next* day's recovery drops by ~15 after alcohol.
        outcomes[day + dt.timedelta(days=1)] = 65 - (15 if drank else 0) + rng.normal(0, 4)
    effects = {e.tag: e for e in tag_effects(tags, outcomes)}
    alcohol = effects["alcohol"]
    assert alcohol.difference < -10
    assert alcohol.confident
    assert alcohol.ci_high < 0
    assert alcohol.n_with == 20
    assert alcohol.n_without == 40


def test_no_difference_is_not_confident() -> None:
    # Same +1/-1 pattern with and without the tag: true difference is zero.
    tags = {d: (["nap"] if i % 2 else []) for i, d in enumerate(_days(32))}
    outcomes = {
        d + dt.timedelta(days=1): 60.0 + (1 if i % 4 in (0, 1) else -1)
        for i, d in enumerate(_days(32))
    }
    nap = next(e for e in tag_effects(tags, outcomes) if e.tag == "nap")
    assert nap.difference == 0
    assert not nap.confident


def test_needs_enough_days_with_and_without() -> None:
    tags = {d: (["sauna"] if i < 3 else []) for i, d in enumerate(_days(20))}
    outcomes = {d + dt.timedelta(days=1): 60.0 for d in _days(20)}
    assert tag_effects(tags, outcomes, min_days=5) == []


def test_days_without_next_day_outcome_are_ignored() -> None:
    tags = {d: ["travel"] if i % 2 else ["home"] for i, d in enumerate(_days(20))}
    outcomes: dict[dt.date, float | None] = {
        d + dt.timedelta(days=1): (None if i < 10 else 60.0 + i) for i, d in enumerate(_days(20))
    }
    effects = {e.tag: e for e in tag_effects(tags, outcomes)}
    assert effects["travel"].n_with + effects["travel"].n_without == 10


def test_sorted_by_size_of_effect() -> None:
    tags = {d: (["a", "b"] if i % 2 else []) for i, d in enumerate(_days(40))}
    outcomes = {
        d + dt.timedelta(days=1): (70.0 if i % 2 else 60.0) for i, d in enumerate(_days(40))
    }
    tags.update({d: ["small"] for d in _days(40)[::4]})
    differences = [abs(e.difference) for e in tag_effects(tags, outcomes)]
    assert differences == sorted(differences, reverse=True)
