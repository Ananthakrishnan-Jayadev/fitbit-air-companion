"""Recovery (0-100) from today's physiology compared with personal baselines.

Components map z-scores to 0-100 around 50 (each SD moves 20 points):
- HRV (40%): higher is better
- resting HR (25%): lower is better
- sleep performance (25%): used as-is
- respiratory rate (10%): lower is better
Penalties: skin temperature >= +0.5 °C above baseline (-10), SpO2 z <= -2 (-5).
Needs HRV or resting HR; otherwise there is no score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

WEIGHTS = {"hrv": 0.40, "resting_hr": 0.25, "sleep": 0.25, "respiratory_rate": 0.10}
POINTS_PER_SD = 20.0
TEMP_PENALTY_THRESHOLD_C = 0.5
TEMP_PENALTY = 10.0
SPO2_PENALTY_Z = -2.0
SPO2_PENALTY = 5.0


@dataclass(frozen=True)
class RecoveryInput:
    hrv_z: float | None = None
    rhr_z: float | None = None
    resp_z: float | None = None
    spo2_z: float | None = None
    temp_delta_c: float | None = None
    sleep_perf: float | None = None


@dataclass(frozen=True)
class Recovery:
    score: float | None
    components: dict[str, float | None] = field(default_factory=dict)
    penalties: dict[str, float] = field(default_factory=dict)


def recovery_score(inputs: RecoveryInput) -> Recovery:
    components: dict[str, float | None] = {
        "hrv": _from_z(inputs.hrv_z, higher_is_better=True),
        "resting_hr": _from_z(inputs.rhr_z, higher_is_better=False),
        "sleep": inputs.sleep_perf,
        "respiratory_rate": _from_z(inputs.resp_z, higher_is_better=False),
    }
    if components["hrv"] is None and components["resting_hr"] is None:
        return Recovery(None, components)

    present = {k: v for k, v in components.items() if v is not None}
    total_weight = sum(WEIGHTS[k] for k in present)
    score = sum(WEIGHTS[k] * v for k, v in present.items()) / total_weight

    penalties: dict[str, float] = {}
    if inputs.temp_delta_c is not None and inputs.temp_delta_c >= TEMP_PENALTY_THRESHOLD_C:
        penalties["temperature"] = TEMP_PENALTY
    if inputs.spo2_z is not None and inputs.spo2_z <= SPO2_PENALTY_Z:
        penalties["spo2"] = SPO2_PENALTY
    score -= sum(penalties.values())
    return Recovery(round(min(100.0, max(0.0, score)), 1), components, penalties)


def _from_z(z: float | None, *, higher_is_better: bool) -> float | None:
    if z is None:
        return None
    signed = z if higher_is_better else -z
    return min(100.0, max(0.0, 50 + POINTS_PER_SD * signed))
