from fitbit_app.analytics.anomaly import detect_anomalies

NORMAL = {"hrv_z": 0.0, "rhr_z": 0.0, "resp_z": 0.0, "spo2_z": 0.0, "temp_delta_c": 0.0}


def test_normal_day_has_no_flags() -> None:
    result = detect_anomalies(**NORMAL)
    assert result.flags == []
    assert result.illness_risk == 0


def test_fever_with_high_resting_hr_is_illness_watch() -> None:
    result = detect_anomalies(**{**NORMAL, "temp_delta_c": 0.8, "rhr_z": 2.5})
    assert "temp_elevated" in result.flags
    assert "rhr_elevated" in result.flags
    assert "illness_watch" in result.flags
    assert result.illness_risk == 0.55


def test_temperature_alone_is_not_illness_watch() -> None:
    result = detect_anomalies(**{**NORMAL, "temp_delta_c": 0.8})
    assert result.flags == ["temp_elevated"]


def test_three_signals_without_temperature_is_illness_watch() -> None:
    result = detect_anomalies(**{**NORMAL, "rhr_z": 2.1, "hrv_z": -2.0, "spo2_z": -2.5})
    assert "illness_watch" in result.flags


def test_hrv_streak() -> None:
    result = detect_anomalies(**{**NORMAL, "hrv_z": -1.2}, recent_hrv_z=[-1.1, -1.3])
    assert "hrv_suppressed_3d" in result.flags
    broken = detect_anomalies(**{**NORMAL, "hrv_z": -1.2}, recent_hrv_z=[None, -1.3])
    assert "hrv_suppressed_3d" not in broken.flags


def test_missing_inputs_raise_nothing() -> None:
    result = detect_anomalies(hrv_z=None, rhr_z=None, resp_z=None, spo2_z=None, temp_delta_c=None)
    assert result.flags == []
