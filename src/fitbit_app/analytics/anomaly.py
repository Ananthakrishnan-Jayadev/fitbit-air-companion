"""Illness / overreach flags from deviations against personal baselines.

Not a diagnosis: these mark days worth paying attention to.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

TEMP_ELEVATED_C = 0.5
RHR_ELEVATED_Z = 2.0
HRV_SUPPRESSED_Z = -1.5
RESP_ELEVATED_Z = 2.0
SPO2_LOW_Z = -2.0
STREAK_HRV_Z = -1.0
STREAK_DAYS = 3

# Contribution of each signal to illness_risk (sums to 1).
RISK_WEIGHTS = {
    "temp_elevated": 0.30,
    "rhr_elevated": 0.25,
    "hrv_suppressed": 0.20,
    "resp_elevated": 0.15,
    "spo2_low": 0.10,
}


@dataclass(frozen=True)
class AnomalyResult:
    flags: list[str] = field(default_factory=list)
    illness_risk: float = 0.0  # 0..1


def detect_anomalies(
    *,
    hrv_z: float | None,
    rhr_z: float | None,
    resp_z: float | None,
    spo2_z: float | None,
    temp_delta_c: float | None,
    recent_hrv_z: Sequence[float | None] = (),
) -> AnomalyResult:
    """`recent_hrv_z`: HRV z-scores of the preceding days, oldest first (today excluded)."""
    signals = {
        "temp_elevated": temp_delta_c is not None and temp_delta_c >= TEMP_ELEVATED_C,
        "rhr_elevated": rhr_z is not None and rhr_z >= RHR_ELEVATED_Z,
        "hrv_suppressed": hrv_z is not None and hrv_z <= HRV_SUPPRESSED_Z,
        "resp_elevated": resp_z is not None and resp_z >= RESP_ELEVATED_Z,
        "spo2_low": spo2_z is not None and spo2_z <= SPO2_LOW_Z,
    }
    flags = [name for name, on in signals.items() if on]

    cardio = signals["rhr_elevated"] or signals["hrv_suppressed"] or signals["resp_elevated"]
    if (signals["temp_elevated"] and cardio) or len(flags) >= 3:
        flags.append("illness_watch")

    streak = [*recent_hrv_z[-(STREAK_DAYS - 1) :], hrv_z]
    if len(streak) == STREAK_DAYS and all(z is not None and z <= STREAK_HRV_Z for z in streak):
        flags.append(f"hrv_suppressed_{STREAK_DAYS}d")

    risk = sum(RISK_WEIGHTS[name] for name, on in signals.items() if on)
    return AnomalyResult(flags, round(risk, 2))
