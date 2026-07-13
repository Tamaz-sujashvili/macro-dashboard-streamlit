"""Persistent, point-in-time consensus history and regime flip detection.

This module deliberately contains no Streamlit code.  Detector histories are
aligned causally, consensus is calculated with the same confidence-weighted
vote as :func:`modules.regime_engine.compute_consensus`, and the resulting
history/alert log are kept in the project ``.cache`` directory.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from modules.regime_engine import RegimeSignal


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CACHE_DIR = _PROJECT_ROOT / ".cache"
CONSENSUS_HISTORY_PATH = _CACHE_DIR / "consensus_history.parquet"
ALERT_LOG_PATH = _CACHE_DIR / "alert_log.parquet"

_HISTORY_COLUMNS = ["date", "timeframe", "risk_score", "label", "n", "agreement"]
_ALERT_COLUMNS = [
    "date",
    "timeframe",
    "detector",
    "from_label",
    "to_label",
    "risk_score",
    "n",
]


@dataclass(frozen=True)
class FlipEvent:
    """A consensus or detector state transition."""

    date: dt.date
    timeframe: str
    from_label: str
    to_label: str
    risk_score: float
    n: int
    detector: Optional[str] = None


def _empty_history() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "timeframe": pd.Series(dtype="object"),
            "risk_score": pd.Series(dtype="float64"),
            "label": pd.Series(dtype="object"),
            "n": pd.Series(dtype="int64"),
            "agreement": pd.Series(dtype="float64"),
        },
        columns=_HISTORY_COLUMNS,
    )


def _empty_alert_log() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "timeframe": pd.Series(dtype="object"),
            "detector": pd.Series(dtype="object"),
            "from_label": pd.Series(dtype="object"),
            "to_label": pd.Series(dtype="object"),
            "risk_score": pd.Series(dtype="float64"),
            "n": pd.Series(dtype="int64"),
        },
        columns=_ALERT_COLUMNS,
    )


def _normalise_dates(values: pd.Series) -> pd.Series:
    """Return timezone-free midnight timestamps without raising on bad input."""
    parsed = pd.to_datetime(values, errors="coerce", utc=True)
    return parsed.dt.tz_convert(None).dt.normalize()


def _plain_label(score: float) -> str:
    if score > 0.3:
        return "Risk-On"
    if score < -0.3:
        return "Risk-Off"
    return "Neutral"


def _signal_value(signal: Any, name: str, default: Any = None) -> Any:
    if isinstance(signal, Mapping):
        return signal.get(name, default)
    return getattr(signal, name, default)


def _normalise_detector_history(signal: Any) -> Optional[pd.DataFrame]:
    history = _signal_value(signal, "history")
    if not isinstance(history, pd.DataFrame) or history.empty:
        return None
    if not {"date", "risk_score"}.issubset(history.columns):
        return None

    frame = history.copy()
    frame["date"] = _normalise_dates(frame["date"])
    frame["risk_score"] = pd.to_numeric(frame["risk_score"], errors="coerce")
    frame = frame.dropna(subset=["date", "risk_score"])
    if frame.empty:
        return None

    if "state" not in frame.columns:
        frame["state"] = frame["risk_score"].map(_plain_label)
    else:
        derived = frame["risk_score"].map(_plain_label)
        frame["state"] = frame["state"].where(frame["state"].notna(), derived).astype(str)

    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    frame["detector"] = str(_signal_value(signal, "detector_name", "Unknown"))
    frame["timeframe"] = str(_signal_value(signal, "timeframe", "D"))
    try:
        confidence = float(_signal_value(signal, "confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    frame["confidence"] = float(np.clip(confidence, 0.0, 1.0))
    return frame[["date", "risk_score", "state", "detector", "timeframe", "confidence"]]


def _detector_frames(signals: Optional[Sequence[RegimeSignal]]) -> List[pd.DataFrame]:
    if signals is None:
        return []
    frames: List[pd.DataFrame] = []
    for signal in signals:
        frame = _normalise_detector_history(signal)
        if frame is not None and not frame.empty:
            frames.append(frame)
    return frames


def _vote(score_values: pd.Series, confidences: pd.Series) -> tuple[float, int, float, str]:
    valid = pd.to_numeric(score_values, errors="coerce").notna()
    scores = pd.to_numeric(score_values[valid], errors="coerce")
    weights = pd.to_numeric(confidences[valid], errors="coerce").fillna(0.0).clip(lower=0.0)
    weights = weights.clip(lower=0.01)
    n = int(scores.shape[0])
    if n == 0:
        return 0.0, 0, 0.0, "No Data"

    weighted_score = float((scores * weights).sum() / weights.sum())
    consensus_sign = np.sign(weighted_score)
    if consensus_sign == 0:
        agree = int((scores.abs() < 0.15).sum())
    else:
        agree = int((np.sign(scores) == consensus_sign).sum())
    agreement = float(agree / n)
    return weighted_score, n, agreement, _plain_label(weighted_score)


def _compute_fresh_history(frames: Sequence[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return _empty_history()

    records: List[dict[str, Any]] = []
    timeframes = sorted({str(frame["timeframe"].iloc[0]) for frame in frames})
    for timeframe in timeframes:
        tf_frames = [frame for frame in frames if str(frame["timeframe"].iloc[0]) == timeframe]
        dates = pd.DatetimeIndex(sorted(set().union(*(set(frame["date"]) for frame in tf_frames))))
        if len(dates) == 0:
            continue

        aligned: List[pd.Series] = []
        states: List[pd.Series] = []
        confidence: List[float] = []
        for frame in tf_frames:
            indexed = frame.set_index("date")
            values = indexed["risk_score"].reindex(dates)
            state_values = indexed["state"].reindex(dates)
            if timeframe.upper() == "D":
                # ``dates`` is the outer union of detector observations, so a
                # limit of five means five observed trading-date rows.
                values = values.ffill(limit=5)
                state_values = state_values.ffill(limit=5)
            aligned.append(values.rename(str(frame["detector"].iloc[0])))
            states.append(state_values.rename(str(frame["detector"].iloc[0])))
            confidence.append(float(frame["confidence"].iloc[0]))

        score_frame = pd.concat(aligned, axis=1)
        state_frame = pd.concat(states, axis=1)
        # Match ``compute_consensus``: a detector in ``No Data`` does not
        # contribute a neutral zero or inflate the detector count.  Apply the
        # state mask after daily forward filling so an explicit No-Data
        # observation also clears a prior score.
        score_frame = score_frame.mask(state_frame.eq("No Data"))
        confidence_series = pd.Series(confidence, index=score_frame.columns, dtype=float)
        for date in dates:
            score, n, agreement, label = _vote(score_frame.loc[date], confidence_series)
            records.append(
                {
                    "date": date,
                    "timeframe": timeframe,
                    "risk_score": round(score, 4),
                    "label": label,
                    "n": n,
                    "agreement": round(agreement, 4),
                }
            )

    if not records:
        return _empty_history()
    result = pd.DataFrame(records, columns=_HISTORY_COLUMNS)
    result["date"] = pd.to_datetime(result["date"]).dt.normalize()
    result["n"] = result["n"].astype(int)
    return result.sort_values(["date", "timeframe"]).reset_index(drop=True)


def _load_history(path: Path) -> pd.DataFrame:
    try:
        if not path.exists():
            return _empty_history()
        frame = pd.read_parquet(path)
        if not set(_HISTORY_COLUMNS).issubset(frame.columns):
            return _empty_history()
        frame = frame[_HISTORY_COLUMNS].copy()
        frame["date"] = _normalise_dates(frame["date"])
        frame["risk_score"] = pd.to_numeric(frame["risk_score"], errors="coerce")
        frame["n"] = pd.to_numeric(frame["n"], errors="coerce").fillna(0).astype(int)
        frame["agreement"] = pd.to_numeric(frame["agreement"], errors="coerce").fillna(0.0)
        return frame.dropna(subset=["date"]).sort_values(["date", "timeframe"]).reset_index(drop=True)
    except Exception:
        return _empty_history()


def load_alert_log(path: Optional[Path] = None) -> pd.DataFrame:
    """Load the persisted alert log without raising on missing/corrupt data."""
    target = Path(path) if path is not None else Path(ALERT_LOG_PATH)
    try:
        if not target.exists():
            return _empty_alert_log()
        frame = pd.read_parquet(target)
        if not set(_ALERT_COLUMNS).issubset(frame.columns):
            return _empty_alert_log()
        frame = frame[_ALERT_COLUMNS].copy()
        frame["date"] = _normalise_dates(frame["date"])
        frame["risk_score"] = pd.to_numeric(frame["risk_score"], errors="coerce")
        frame["n"] = pd.to_numeric(frame["n"], errors="coerce").fillna(0).astype(int)
        return frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    except Exception:
        return _empty_alert_log()


def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
    except Exception:
        # Cache persistence must never turn missing optional parquet engines or
        # an unwritable cache directory into a dashboard failure.
        return


def build_consensus_history(signals: Optional[Sequence[RegimeSignal]]) -> pd.DataFrame:
    """Build and persist a causal per-timeframe consensus history.

    Existing rows before the ten-business-day revision window are retained
    verbatim.  The current detector histories are always recomputed for that
    tail, which absorbs revised source data while allowing the history to grow
    incrementally.
    """
    frames = _detector_frames(signals)
    fresh = _compute_fresh_history(frames)
    if fresh.empty:
        return _empty_history()

    cache_path = Path(CONSENSUS_HISTORY_PATH)
    cached = _load_history(cache_path)
    if cached.empty:
        result = fresh
    else:
        latest = fresh["date"].max()
        recompute_start = latest - pd.offsets.BDay(9)
        preserved = cached[cached["date"] < recompute_start]
        revised_tail = fresh[fresh["date"] >= recompute_start]
        result = pd.concat([preserved, revised_tail], ignore_index=True)
        result = result.drop_duplicates(["date", "timeframe"], keep="last")
        result = result.sort_values(["date", "timeframe"]).reset_index(drop=True)

    result = result[_HISTORY_COLUMNS]
    result["n"] = result["n"].astype(int)
    _write_parquet(result, cache_path)
    # DataFrame attrs keep detector context available for detector-level flip
    # detection without changing the persisted consensus schema.
    result.attrs["_detector_histories"] = [frame.copy() for frame in frames]
    return result


def apply_hysteresis(scores: pd.Series) -> pd.Series:
    """Apply asymmetric Risk-On/Risk-Off entry and exit bands."""
    if not isinstance(scores, pd.Series) or scores.empty:
        return pd.Series(index=getattr(scores, "index", None), dtype="object", name=getattr(scores, "name", None))

    labels: List[str] = []
    previous: Optional[str] = None
    for raw_score in pd.to_numeric(scores, errors="coerce"):
        score = float(raw_score) if pd.notna(raw_score) else None
        if previous is None:
            previous = _plain_label(score) if score is not None else "Neutral"
        elif score is not None:
            if score > 0.35:
                previous = "Risk-On"
            elif score < -0.35:
                previous = "Risk-Off"
            elif previous == "Risk-On" and score < 0.25:
                previous = "Neutral"
            elif previous == "Risk-Off" and score > -0.25:
                previous = "Neutral"
        labels.append(previous)
    return pd.Series(labels, index=scores.index, name=scores.name, dtype="object")


def _detector_frames_from_history(history: pd.DataFrame) -> List[pd.DataFrame]:
    attached = history.attrs.get("_detector_histories", []) if isinstance(history, pd.DataFrame) else []
    if attached:
        return [frame.copy() for frame in attached if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not isinstance(history, pd.DataFrame) or "detector" not in history.columns:
        return []
    if "date" not in history.columns or "risk_score" not in history.columns:
        return []

    frames = []
    group_columns = ["detector"] + (["timeframe"] if "timeframe" in history.columns else [])
    for _, group in history.groupby(group_columns, dropna=False):
        frame = group.copy()
        frame["date"] = _normalise_dates(frame["date"])
        if "state" not in frame.columns:
            frame["state"] = pd.to_numeric(frame["risk_score"], errors="coerce").map(_plain_label)
        frames.append(frame)
    return frames


def detect_flips(history: Optional[pd.DataFrame]) -> List[FlipEvent]:
    """Return consensus hysteresis flips and recent detector state changes."""
    if not isinstance(history, pd.DataFrame) or history.empty:
        return []
    required = {"date", "timeframe", "risk_score"}
    if not required.issubset(history.columns):
        return []

    events: List[FlipEvent] = []
    consensus = history.copy()
    consensus["date"] = _normalise_dates(consensus["date"])
    consensus["risk_score"] = pd.to_numeric(consensus["risk_score"], errors="coerce")
    if "n" in consensus.columns:
        consensus.loc[pd.to_numeric(consensus["n"], errors="coerce").fillna(0) <= 0, "risk_score"] = np.nan

    for timeframe, group in consensus.dropna(subset=["date"]).groupby("timeframe"):
        group = group.sort_values("date").drop_duplicates("date", keep="last")
        scores = group.set_index("date")["risk_score"].dropna()
        labels = apply_hysteresis(scores)
        for index in range(1, len(labels)):
            if labels.iloc[index] == labels.iloc[index - 1]:
                continue
            event_date = labels.index[index]
            row = group[group["date"] == event_date].iloc[-1]
            events.append(
                FlipEvent(
                    date=event_date.date(),
                    timeframe=str(timeframe),
                    from_label=str(labels.iloc[index - 1]),
                    to_label=str(labels.iloc[index]),
                    risk_score=float(row["risk_score"]),
                    n=int(row.get("n", 0)),
                )
            )

    detector_frames = _detector_frames_from_history(history)
    if detector_frames:
        max_date = max(frame["date"].max() for frame in detector_frames if not frame.empty)
        window_start = max_date - pd.Timedelta(days=30)
        for frame in detector_frames:
            if frame.empty or "state" not in frame.columns:
                continue
            frame = frame.sort_values("date").drop_duplicates("date", keep="last")
            states = frame["state"].astype(str)
            changed = states.ne(states.shift(1)) & states.shift(1).notna()
            for _, row in frame.loc[changed & (frame["date"] >= window_start)].iterrows():
                events.append(
                    FlipEvent(
                        date=row["date"].date(),
                        timeframe=str(row.get("timeframe", "D")),
                        from_label=str(states.shift(1).loc[row.name]),
                        to_label=str(row["state"]),
                        risk_score=float(row["risk_score"]),
                        n=1,
                        detector=str(row.get("detector", "Unknown")),
                    )
                )

    return sorted(events, key=lambda event: (event.date, event.timeframe, event.detector or ""))


def _event_rows(events: Optional[Iterable[FlipEvent]]) -> pd.DataFrame:
    rows = []
    for event in events or []:
        if not isinstance(event, FlipEvent):
            continue
        rows.append(
            {
                "date": pd.Timestamp(event.date),
                "timeframe": event.timeframe,
                "detector": event.detector,
                "from_label": event.from_label,
                "to_label": event.to_label,
                "risk_score": float(event.risk_score),
                "n": int(event.n),
            }
        )
    return pd.DataFrame(rows, columns=_ALERT_COLUMNS)


def append_flips(events: Optional[Iterable[FlipEvent]]) -> pd.DataFrame:
    """Append flip events to the parquet alert log with key-based deduping."""
    incoming = _event_rows(events)
    path = Path(ALERT_LOG_PATH)
    existing = load_alert_log(path)

    if incoming.empty and existing.empty:
        return _empty_alert_log()
    result = pd.concat([existing, incoming], ignore_index=True)
    result["date"] = _normalise_dates(result["date"])
    result = result.drop_duplicates(["date", "timeframe", "detector", "to_label"], keep="last")
    result = result.sort_values(["date", "timeframe", "detector"], na_position="first").reset_index(drop=True)
    _write_parquet(result[_ALERT_COLUMNS], path)
    return result[_ALERT_COLUMNS]
