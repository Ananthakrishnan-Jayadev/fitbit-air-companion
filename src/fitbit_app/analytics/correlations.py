"""What affects you: journal tags vs next-day outcomes.

A tag on day D describes that day (e.g. "alcohol" on Friday). It is compared with the outcome
on day D + 1 (Saturday's recovery, or the night ending Saturday morning for sleep).
Only days with a journal entry count: an un-logged day is unknown, not "tag absent".
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Mapping
from dataclasses import dataclass

import numpy as np

MIN_DAYS = 5
BOOTSTRAP_SAMPLES = 2000


@dataclass(frozen=True)
class TagEffect:
    tag: str
    n_with: int
    n_without: int
    mean_with: float
    mean_without: float
    difference: float  # mean_with - mean_without
    ci_low: float
    ci_high: float

    @property
    def confident(self) -> bool:
        """The 95% interval excludes zero."""
        return self.ci_low > 0 or self.ci_high < 0


def tag_effects(
    tags_by_day: Mapping[dt.date, Collection[str]],
    outcomes: Mapping[dt.date, float | None],
    *,
    lag_days: int = 1,
    min_days: int = MIN_DAYS,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = 0,
) -> list[TagEffect]:
    """Per-tag difference in the outcome `lag_days` later, with a bootstrap 95% CI.

    Tags need at least `min_days` logged days with and without them. Sorted by |difference|.
    """
    lag = dt.timedelta(days=lag_days)
    logged = {
        day: set(tags) for day, tags in tags_by_day.items() if outcomes.get(day + lag) is not None
    }
    rng = np.random.default_rng(seed)
    effects = []
    for tag in sorted({t for tags in logged.values() for t in tags}):
        with_tag = np.array([outcomes[d + lag] for d, tags in logged.items() if tag in tags])
        without = np.array([outcomes[d + lag] for d, tags in logged.items() if tag not in tags])
        if len(with_tag) < min_days or len(without) < min_days:
            continue
        low, high = _bootstrap_ci(with_tag.astype(float), without.astype(float), samples, rng)
        effects.append(
            TagEffect(
                tag=tag,
                n_with=len(with_tag),
                n_without=len(without),
                mean_with=round(float(with_tag.mean()), 2),
                mean_without=round(float(without.mean()), 2),
                difference=round(float(with_tag.mean() - without.mean()), 2),
                ci_low=round(low, 2),
                ci_high=round(high, 2),
            )
        )
    return sorted(effects, key=lambda e: abs(e.difference), reverse=True)


def _bootstrap_ci(
    a: np.ndarray, b: np.ndarray, samples: int, rng: np.random.Generator
) -> tuple[float, float]:
    """95% percentile interval of mean(a) - mean(b), resampling each group."""
    a_means = rng.choice(a, size=(samples, len(a)), replace=True).mean(axis=1)
    b_means = rng.choice(b, size=(samples, len(b)), replace=True).mean(axis=1)
    low, high = np.percentile(a_means - b_means, [2.5, 97.5])
    return float(low), float(high)
