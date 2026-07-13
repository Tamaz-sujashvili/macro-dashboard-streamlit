"""Headless scheduled regime-flip alert runner.

This file intentionally imports no Streamlit module.  It is safe to run from
cron or GitHub Actions with the project virtualenv's plain Python executable.
"""

from __future__ import annotations

import datetime as dt
import sys
import urllib.request
from typing import Iterable

import pandas as pd

from modules.consensus_history import FlipEvent, append_flips, build_consensus_history, detect_flips, load_alert_log
from modules.headless_data import fetch_headless_inputs, get_secret
from modules.regime_engine import (
    compute_consensus,
    hmm_detector,
    liquidity_regime_detector,
    macro_quadrant_adapter,
    trend_vol_detector,
    vol_regime_detector,
)


def _current_consensus_history() -> pd.DataFrame:
    inputs = fetch_headless_inputs()
    spy = inputs.get("spy")
    if not isinstance(spy, pd.DataFrame) or spy.empty:
        raise RuntimeError("SPY history unavailable")
    fred = inputs.get("fred") or {}
    signals = [
        trend_vol_detector(spy, timeframe="D"),
        trend_vol_detector(spy, timeframe="W"),
        hmm_detector(spy),
        vol_regime_detector(inputs.get("vix"), inputs.get("term_structure"), spy),
        liquidity_regime_detector(fred),
        macro_quadrant_adapter(fred),
        inputs.get("breadth"),
    ]
    signals = [signal for signal in signals if signal is not None]
    if not compute_consensus(signals):
        raise RuntimeError("No current regime consensus available")
    history = build_consensus_history(signals)
    if history.empty:
        raise RuntimeError("Consensus history unavailable")
    return history


def compute_current_flips() -> list[FlipEvent]:
    history = _current_consensus_history()
    latest = pd.to_datetime(history["date"], errors="coerce").max()
    if pd.isna(latest):
        return []
    cutoff = latest - pd.Timedelta(days=30)
    # Preserve hysteresis state from before the 30-day alert window, then
    # return only recent events for notification.
    return [event for event in detect_flips(history) if pd.Timestamp(event.date) >= cutoff]


def _event_key(event: FlipEvent) -> tuple[dt.date, str, str | None, str]:
    return event.date, event.timeframe, event.detector, event.to_label


def _event_text(event: FlipEvent) -> str:
    subject = event.timeframe if event.detector is None else f"{event.timeframe}/{event.detector}"
    return (
        f"CONSENSUS FLIP - {subject}: {event.from_label.upper()} -> {event.to_label.upper()} "
        f"({event.date.isoformat()}, score {event.risk_score:+.2f})"
    )


def _post_ntfy(topic: str, body: str) -> None:
    request = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        method="POST",
        headers={"Title": "Macro Regime Terminal", "Content-Type": "text/plain; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status >= 300:
            raise RuntimeError(f"ntfy returned HTTP {response.status}")


def _new_flips(events: Iterable[FlipEvent]) -> list[FlipEvent]:
    logged = {_event_key(event) for event in []}
    log = load_alert_log()
    if not log.empty:
        for row in log.itertuples(index=False):
            logged.add((pd.Timestamp(row.date).date(), str(row.timeframe), row.detector if pd.notna(row.detector) else None, str(row.to_label)))
    return [event for event in events if _event_key(event) not in logged]


def main() -> int:
    try:
        new_flips = _new_flips(compute_current_flips())
        if not new_flips:
            print("ALERTS: ran successfully; no new flips")
            return 0

        topic = get_secret("NTFY_TOPIC")
        for event in new_flips:
            text = _event_text(event)
            if topic:
                _post_ntfy(topic, text)
            else:
                print(f"ALERT: {text}")
            # Persist immediately after a successful delivery.  If a later
            # notification fails, rerunning will not duplicate earlier sends.
            append_flips([event])
        delivery = "sent" if topic else "printed"
        print(f"ALERTS: ran successfully; {delivery}={len(new_flips)} new_flip(s)")
        return 0
    except Exception as exc:
        print(f"ALERTS: data failure; {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
