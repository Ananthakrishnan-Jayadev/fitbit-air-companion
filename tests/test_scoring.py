import datetime as dt
import statistics

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.scoring import RECENT_DAYS, ScoreService
from fitbit_app.storage.models import Baseline, DailyMetric, ExerciseSession, HrSample, Score
from fixtures.db_seed import seed
from fixtures.synthetic import generate

START = dt.date(2026, 9, 1)
DAYS = 21
SICK = START + dt.timedelta(days=18)
NOW = dt.datetime.combine(START + dt.timedelta(days=DAYS), dt.time(), tzinfo=dt.UTC)


@pytest.fixture
def seeded(session_factory: sessionmaker[Session]) -> sessionmaker[Session]:
    seed(session_factory, generate(START, DAYS, seed=5, sick_days={SICK}))
    return session_factory


@pytest.fixture
def service(seeded: sessionmaker[Session]) -> ScoreService:
    return ScoreService(seeded, clock=lambda: NOW)


def _scores(session_factory: sessionmaker[Session]) -> dict[dt.date, Score]:
    with session_factory() as session:
        return {s.date: s for s in session.scalars(select(Score)).all()}


def test_scores_every_day(service: ScoreService, seeded: sessionmaker[Session]) -> None:
    assert service.recompute_all() == DAYS
    scores = _scores(seeded)
    assert sorted(scores) == [START + dt.timedelta(days=i) for i in range(DAYS)]
    for score in scores.values():
        assert score.sleep_perf is not None and 0 <= score.sleep_perf <= 100
        assert score.components_json is not None


def test_recovery_needs_a_week_of_baseline(
    service: ScoreService, seeded: sessionmaker[Session]
) -> None:
    service.recompute_all()
    scores = _scores(seeded)
    assert scores[START + dt.timedelta(days=3)].recovery is None
    for i in range(7, DAYS):
        recovery = scores[START + dt.timedelta(days=i)].recovery
        assert recovery is not None and 0 <= recovery <= 100


def test_sick_day_is_flagged_and_scores_low(
    service: ScoreService, seeded: sessionmaker[Session]
) -> None:
    service.recompute_all()
    scores = _scores(seeded)
    sick = scores[SICK]
    assert sick.components_json is not None
    assert "temp_elevated" in sick.components_json["flags"]
    assert "illness_watch" in sick.components_json["flags"]
    assert sick.illness_risk is not None and sick.illness_risk >= 0.5
    others = [s.recovery for d, s in scores.items() if d != SICK and s.recovery is not None]
    assert sick.recovery is not None
    assert sick.recovery < statistics.median(others)


def test_strain_and_targets(service: ScoreService, seeded: sessionmaker[Session]) -> None:
    service.recompute_all()
    scores = _scores(seeded).values()
    strains = [s.strain for s in scores if s.strain is not None]
    assert strains and max(strains) > 5
    assert all(0 <= s <= 21 for s in strains)
    with_recovery = [s for s in scores if s.recovery is not None]
    assert all(s.strain_target_low is not None for s in with_recovery)


def test_baselines_and_derived_columns(
    service: ScoreService, seeded: sessionmaker[Session]
) -> None:
    service.recompute_all()
    last = START + dt.timedelta(days=DAYS - 1)
    with seeded() as session:
        metrics = set(session.scalars(select(Baseline.metric).where(Baseline.as_of == last)))
        assert {"resting_hr", "hrv_rmssd_ms", "spo2_avg"} <= metrics
        row = session.get(DailyMetric, last)
        assert row is not None
        assert row.sleep_min is not None and row.sleep_min > 200


def test_workout_max_hr_from_samples(service: ScoreService, seeded: sessionmaker[Session]) -> None:
    service.recompute_all()
    with seeded() as session:
        workout = session.scalars(select(ExerciseSession)).first()
        assert workout is not None
        expected = session.scalar(
            select(func.max(HrSample.bpm)).where(
                HrSample.ts >= workout.start_ts, HrSample.ts < workout.end_ts
            )
        )
        assert workout.max_hr == expected


def test_rerun_is_idempotent(service: ScoreService, seeded: sessionmaker[Session]) -> None:
    service.recompute_all()
    first = {d: s.recovery for d, s in _scores(seeded).items()}
    service.recompute_all()
    assert {d: s.recovery for d, s in _scores(seeded).items()} == first


def test_after_sync_rescoring(service: ScoreService) -> None:
    assert service.recompute_after_sync() == DAYS  # nothing scored yet -> everything
    assert service.recompute_after_sync() == RECENT_DAYS


def test_after_sync_fills_unscored_gaps(
    service: ScoreService, seeded: sessionmaker[Session]
) -> None:
    service.recompute_all()
    gap = [START + dt.timedelta(days=i) for i in range(5, 10)]
    with seeded() as session:
        session.execute(delete(Score).where(Score.date.in_(gap)))
        session.commit()

    assert service.recompute_after_sync() == RECENT_DAYS + len(gap)
    assert set(gap) <= set(_scores(seeded))


def test_empty_database(session_factory: sessionmaker[Session]) -> None:
    service = ScoreService(session_factory, clock=lambda: NOW)
    assert service.recompute_all() == 0
    assert service.recompute_after_sync() == 0
