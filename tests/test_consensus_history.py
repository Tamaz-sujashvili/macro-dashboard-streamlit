"""Synthetic tests for persistent consensus history and flip detection."""

import datetime as dt

import pandas as pd

from modules.consensus_history import (
    FlipEvent,
    append_flips,
    apply_hysteresis,
    build_consensus_history,
    detect_flips,
)
from modules.regime_engine import RegimeSignal


def _signal(name, timeframe, dates, scores, confidence=1.0, states=None):
    history = pd.DataFrame({"date": dates, "risk_score": scores})
    if states is not None:
        history["state"] = states
    return RegimeSignal(
        detector_name=name,
        timeframe=timeframe,
        state="Synthetic",
        risk_score=float(scores[-1]),
        confidence=confidence,
        color="#000000",
        as_of=pd.Timestamp(dates[-1]).date(),
        history=history,
    )


def test_daily_consensus_aligns_causally_and_matches_weighted_vote(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.consensus_history.CONSENSUS_HISTORY_PATH", tmp_path / "consensus.parquet")
    dates = pd.date_range("2025-01-02", periods=4, freq="B")
    first = _signal("A", "D", [dates[0], dates[2]], [0.8, 0.8], confidence=1.0)
    second = _signal("B", "D", [dates[0], dates[1], dates[3]], [0.2, -0.2, -0.2], confidence=0.5)

    result = build_consensus_history([first, second])

    assert list(result.columns) == ["date", "timeframe", "risk_score", "label", "n", "agreement"]
    assert result["date"].tolist() == list(dates)
    # A is forward-filled from day 1 through day 4; B is present on day 1.
    # (0.8*1.0 + 0.2*0.5) / 1.5 = 0.6.
    assert result.iloc[0].risk_score == 0.6
    assert result.iloc[0].label == "Risk-On"
    assert result.iloc[0].n == 2
    assert result.iloc[0].agreement == 1.0
    # B has no value on day 3, but its day-2 value is retained by the outer
    # alignment; day 4 uses B's own latest value.  Both are -0.2 here.
    assert result.iloc[2].risk_score == 0.4667
    assert result.iloc[3].risk_score == 0.4667


def test_hysteresis_suppresses_neutral_oscillation():
    scores = pd.Series([0.28, 0.33, 0.28, 0.33, 0.28], index=pd.date_range("2025-01-01", periods=5))
    labels = apply_hysteresis(scores)
    assert labels.tolist() == ["Neutral"] * 5


def test_no_data_history_rows_do_not_dilute_or_count_as_detectors(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.consensus_history.CONSENSUS_HISTORY_PATH", tmp_path / "consensus.parquet")
    dates = pd.date_range("2025-01-01", periods=2, freq="B")
    signal = _signal("HMM", "D", dates, [0.0, 0.8], states=["No Data", "Low-Vol Bull"])

    history = build_consensus_history([signal])

    assert history.iloc[0].label == "No Data"
    assert history.iloc[0].n == 0
    assert history.iloc[1].risk_score == 0.8
    assert history.iloc[1].n == 1


def test_hysteresis_clean_cross_has_exactly_two_flips(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.consensus_history.CONSENSUS_HISTORY_PATH", tmp_path / "consensus.parquet")
    dates = pd.date_range("2025-01-01", periods=3, freq="B")
    signal = _signal("A", "D", dates, [0.0, 0.4, 0.2])
    history = build_consensus_history([signal])

    events = detect_flips(history)
    consensus_events = [event for event in events if event.detector is None]
    assert [(event.from_label, event.to_label) for event in consensus_events] == [
        ("Neutral", "Risk-On"),
        ("Risk-On", "Neutral"),
    ]
    assert len(consensus_events) == 2


def test_detector_flips_are_recent_and_include_detector_name(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.consensus_history.CONSENSUS_HISTORY_PATH", tmp_path / "consensus.parquet")
    dates = pd.date_range("2025-01-01", periods=35, freq="D")
    states = ["Old"] * 33 + ["New", "New"]
    signal = _signal("A", "D", dates, [0.1] * 35, states=states)

    events = detect_flips(build_consensus_history([signal]))
    detector_events = [event for event in events if event.detector == "A"]
    assert len(detector_events) == 1
    assert detector_events[0].from_label == "Old"
    assert detector_events[0].to_label == "New"


def test_parquet_round_trip_and_incremental_extension(tmp_path, monkeypatch):
    cache_path = tmp_path / "consensus.parquet"
    monkeypatch.setattr("modules.consensus_history.CONSENSUS_HISTORY_PATH", cache_path)
    dates = pd.date_range("2025-01-01", periods=20, freq="B")
    first = _signal("A", "D", dates, [0.4] * len(dates))
    initial = build_consensus_history([first])
    assert cache_path.exists()
    assert pd.read_parquet(cache_path).equals(initial)

    extended_dates = pd.date_range("2025-01-01", periods=22, freq="B")
    revised = _signal("A", "D", extended_dates, [-0.4] + [0.4] * 21)
    extended = build_consensus_history([revised])
    assert len(extended) == 22
    # The first date is outside the ten-business-day revision window and is
    # therefore retained from the original cache.
    assert extended.iloc[0].risk_score == 0.4
    assert extended.iloc[-1].date == extended_dates[-1]


def test_alert_log_appends_and_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.consensus_history.ALERT_LOG_PATH", tmp_path / "alerts.parquet")
    event = FlipEvent(dt.date(2025, 1, 2), "D", "Neutral", "Risk-On", 0.4, 1)
    first = append_flips([event])
    second = append_flips([event])
    assert len(first) == len(second) == 1
    assert pd.read_parquet(tmp_path / "alerts.parquet").shape[0] == 1


def test_empty_or_missing_history_is_safe(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.consensus_history.CONSENSUS_HISTORY_PATH", tmp_path / "consensus.parquet")
    empty = build_consensus_history([])
    missing = build_consensus_history([RegimeSignal("A", "D", "No Data", 0, 0, "#000", dt.date.today())])
    assert empty.empty
    assert missing.empty
    assert detect_flips(empty) == []
