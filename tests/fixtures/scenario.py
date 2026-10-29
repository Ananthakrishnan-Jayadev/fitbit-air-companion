"""A seeded + scored synthetic database shared by AI tests."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.scoring import ScoreService
from fixtures.db_seed import seed
from fixtures.synthetic import generate

START = dt.date(2026, 9, 1)  # a Tuesday
DAYS = 21
SICK = START + dt.timedelta(days=18)
LAST = START + dt.timedelta(days=DAYS - 1)  # Monday 2026-09-21
NOW = dt.datetime.combine(START + dt.timedelta(days=DAYS), dt.time(), tzinfo=dt.UTC)


def build_scored_db(session_factory: sessionmaker[Session]) -> None:
    seed(session_factory, generate(START, DAYS, seed=5, sick_days={SICK}))
    ScoreService(session_factory, clock=lambda: NOW).recompute_all()
