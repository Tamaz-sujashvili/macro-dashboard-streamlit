"""Headless alert runner tests with the ntfy delivery mocked."""

import datetime as dt

import pandas as pd

import alerts_runner
from modules import consensus_history
from modules.consensus_history import FlipEvent, append_flips


def _event():
    return FlipEvent(dt.date(2026, 7, 13), "D", "Risk-On", "Risk-Off", -0.41, 3)


def _history():
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-07-10", "2026-07-13"]),
            "timeframe": ["D", "D"],
            "risk_score": [0.4, -0.41],
            "label": ["Risk-On", "Risk-Off"],
            "n": [3, 3],
            "agreement": [1.0, 1.0],
        }
    )


def test_new_flip_triggers_exactly_one_ntfy_send(tmp_path, monkeypatch):
    monkeypatch.setattr(consensus_history, "ALERT_LOG_PATH", tmp_path / "alerts.parquet")
    sent = []
    monkeypatch.setattr(alerts_runner, "compute_current_flips", lambda: [_event()])
    monkeypatch.setattr(alerts_runner, "get_secret", lambda name: "private-topic" if name == "NTFY_TOPIC" else None)
    monkeypatch.setattr(alerts_runner, "_post_ntfy", lambda topic, body: sent.append((topic, body)))

    assert alerts_runner.main() == 0
    assert len(sent) == 1
    assert sent[0][0] == "private-topic"
    assert "RISK-ON -> RISK-OFF" in sent[0][1]


def test_already_logged_flip_triggers_zero_sends(tmp_path, monkeypatch):
    monkeypatch.setattr(consensus_history, "ALERT_LOG_PATH", tmp_path / "alerts.parquet")
    append_flips([_event()])
    sent = []
    monkeypatch.setattr(alerts_runner, "compute_current_flips", lambda: [_event()])
    monkeypatch.setattr(alerts_runner, "get_secret", lambda _name: "private-topic")
    monkeypatch.setattr(alerts_runner, "_post_ntfy", lambda topic, body: sent.append((topic, body)))

    assert alerts_runner.main() == 0
    assert sent == []


def test_data_failure_returns_one_without_raising(monkeypatch, capsys):
    monkeypatch.setattr(alerts_runner, "compute_current_flips", lambda: (_ for _ in ()).throw(RuntimeError("feed unavailable")))

    assert alerts_runner.main() == 1
    assert "data failure" in capsys.readouterr().out


def test_partial_delivery_logs_each_success_before_a_later_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(consensus_history, "ALERT_LOG_PATH", tmp_path / "alerts.parquet")
    first = _event()
    second = FlipEvent(dt.date(2026, 7, 13), "W", "Neutral", "Risk-On", 0.42, 2)
    monkeypatch.setattr(alerts_runner, "compute_current_flips", lambda: [first, second])
    monkeypatch.setattr(alerts_runner, "get_secret", lambda _name: "private-topic")
    sent = []

    def send_then_fail(_topic, body):
        sent.append(body)
        if len(sent) == 2:
            raise RuntimeError("ntfy unavailable")

    monkeypatch.setattr(alerts_runner, "_post_ntfy", send_then_fail)

    assert alerts_runner.main() == 1
    logged = consensus_history.load_alert_log()
    assert len(sent) == 2
    assert len(logged) == 1
    assert logged.iloc[0].timeframe == "D"
