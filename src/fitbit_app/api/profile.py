"""GET/PUT /api/profile: values used by scoring (age, max HR, sleep need)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from fitbit_app.api.deps import get_session
from fitbit_app.storage.models import UserProfile

router = APIRouter(prefix="/profile", tags=["profile"])

PROFILE_ROW_ID = 1

SessionDep = Annotated[Session, Depends(get_session)]


class Profile(BaseModel):
    age: int | None = Field(default=None, ge=10, le=110)
    max_hr: int | None = Field(default=None, ge=100, le=230)
    sleep_need_min: int | None = Field(default=None, ge=240, le=720)


@router.get("", response_model=Profile)
def get_profile(session: SessionDep) -> Profile:
    row = session.get(UserProfile, PROFILE_ROW_ID)
    if row is None:
        return Profile()
    return Profile(age=row.age, max_hr=row.max_hr, sleep_need_min=row.sleep_need_min)


@router.put("", response_model=Profile)
def put_profile(body: Profile, session: SessionDep) -> Profile:
    row = session.get(UserProfile, PROFILE_ROW_ID)
    if row is None:
        row = UserProfile(id=PROFILE_ROW_ID)
        session.add(row)
    row.age = body.age
    row.max_hr = body.max_hr
    row.sleep_need_min = body.sleep_need_min
    session.commit()
    return body
