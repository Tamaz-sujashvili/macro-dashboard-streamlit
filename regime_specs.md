# Macro Dashboard — Implementable Regime-Detection Specifications

**Source repository:** `/Users/tazo/Desktop/quant-alpha-swarm` (read-only extraction)  
**Output file:** `/Users/tazo/Desktop/macro dashboard/regime_specs.md`  
**Extraction date:** 2026-07-11  

> **Scope note:** All exact parameters below are taken directly from the Pine source files or the explicit prompt guidance. Any value not present in those sources is marked `NOT SPECIFIED, propose default X`. The unified-wiki files `concepts/regime-switching-methods.md` and `concepts/regime-detection.md` are stubs or missing; the graphify artifact `graph.json` references a `comparisons/regime-detector-comparison.md` that is **not present in the working tree**, so the "clustering detector" and "Bayesian smoothing detector" nodes cannot be numerically specced from this repo.

---

## (a) TrendVol Detector — Ported from Pine TE v9.1 CORE / v9.4 ADX GATE

### Source logic
- `strategies/pine/te_v9_1_CORE.pine` (lines 54–86, 92–103)
- `strategies/pine/research/READY_TO_USE/TE_v9.4_ADX_GATE_SplitHalf.pine` (lines 28–90)

### Inputs
| Input | Symbol | Source formula |
|-------|--------|----------------|
| Close | `close` | Daily close price |
| High | `high` | Daily high price |
| Low | `low` | Daily low price |
| Volume | `volume` | Daily volume |

### Parameters (exact from Pine)
| Parameter | v9.1 CORE | v9.4 ADX GATE | Meaning |
|-----------|-----------|---------------|---------|
| EMA gate length | `200` | `200` (`emaGateLen`) | Long trend filter |
| Pullback EMA | `20` | `20` (`pbEmaLen`) | Pullback anchor |
| EMA50 | `50` | NOT SPECIFIED | Intermediate trend |
| RSI length | `14` | NOT SPECIFIED | Momentum range gate |
| ATR length | `14` | `14` (`atrLen`) | Volatility measure for stops / pullback depth |
| ADX / DMI length | `14` | `14` | Wilder smoothing length for `ta.dmi(14, 14)` |
| Relative-volume SMA length | `20` | NOT USED | Baseline for volume ratio |
| Breakout lookback | `40` | `20` (`brkLen`) | N-bar high |
| Breakout buffer % | NOT SPECIFIED | `0.1` (`brkBuffer`) | Percent above N-bar high |
| Pullback depth ATR mult | `1.0` (`pbAtr`) | `1.0` (`pbDepthATR`) | Minimum pullback depth |

### Filters and thresholds (exact)
1. **Trend / EMA gate**
   ```text
   v9.1: trendGate = close > ema200 AND ema200 > ema200[5]
   v9.4: aboveGate = close > ema200
   ```
   - Long condition: price is above the 200-day EMA.
   - v9.1 additionally requires the 200-day EMA to be rising over the last 5 bars (`ema200 > ema200[5]`).

2. **ADX filter**
   ```text
   v9.1: adx = ta.dmi(14, 14)[2];  adxPass = adx >= 18.0
   v9.4: adxV = ta.dmi(14, 14)[2]; adxPass = adxV >= 20
   ```
   - Length: **14** (both DMI smoothing length and ADX smoothing length).
   - Threshold: **18** in v9.1 (`minADX`), **20** in v9.4 (`adxThresh`).
   - Direction: **none** — only the magnitude of ADX is used; `+DI`/`-DI` crossover is ignored.
   - Gate is **off by default** in v9.1 (`useADX = false`) and **on by default** in v9.4 (`useADX = true`).

3. **Relative-volume filter**
   ```text
   v9.1: volSma = ta.sma(volume, 20)
         relVol = volume / volSma
         rvPass = relVol >= 1.0
   ```
   - Length: **20**.
   - Threshold: **1.0** (`minRV`).
   - **Not present** in v9.4.

4. **ROC / momentum gate**
   ```text
   v9.1: roc10 = ta.roc(close, 10)
         momPass = roc10 > 0.5
   ```
   - Length: **10**.
   - Threshold: **0.5%** (`momThr`).
   - **Not present** in v9.4.

5. **ATR usage (volatility gating / sizing)**
   - ATR length **14** (`ta.atr(14)`).
   - ATR is **not used as a regime gate**; it scales stop-loss, profit targets, pullback depth, and position sizing.
   - v9.1 stop: `2.5 × ATR14`; TP1: `3.5 × ATR14`; TP2: `6.0 × ATR14`.
   - v9.4 stop: `2.0 × ATR14`; TP1: `3.0 × ATR14`; chandelier trail: `highestHigh(22) − 2.5 × ATR14`.

### Recommended consolidated TrendVol detector for the macro dashboard
Use the **v9.4 ADX GATE** as the stricter baseline and add the v9.1 relative-volume gate as an optional toggle.

```python
import pandas as pd
import numpy as np

def trendvol_regime(df: pd.DataFrame,
                    ema_len: int = 200,
                    adx_len: int = 14,
                    adx_thresh: float = 20.0,
                    rv_len: int = 20,
                    rv_thresh: float = 1.0,
                    use_rv: bool = False) -> pd.Series:
    """
    Returns a daily regime label:
        'trend_vol_confirmed'  : trend gate + ADX pass + (optional RV pass)
        'trend_weak'           : trend gate passes but ADX < thresh
        'below_trend'          : close <= EMA200
    """
    close = df['close']
    volume = df['volume']

    ema200 = close.ewm(span=ema_len, adjust=False).mean()

    # ADX via pandas-ta or equivalent; exact Wilder smoothing length = 14
    adx = df.ta.adx(length=adx_len)['ADX_' + str(adx_len)]

    rv = volume / volume.rolling(rv_len).mean()

    above_gate = close > ema200
    adx_pass = adx >= adx_thresh
    rv_pass = (rv >= rv_thresh) if use_rv else True

    regime = pd.Series('below_trend', index=df.index)
    regime.loc[above_gate & ~(adx_pass & rv_pass)] = 'trend_weak'
    regime.loc[above_gate & adx_pass & rv_pass] = 'trend_vol_confirmed'
    return regime
```

### Output states
- `trend_vol_confirmed` — price above EMA200, ADX ≥ 20, relative volume ≥ 1.0 (if enabled).
- `trend_weak` — price above EMA200 but ADX too low or volume too low.
- `below_trend` — price at or below EMA200.

### Update frequency
Daily, after the daily bar closes (`barstate.isconfirmed` in Pine). No intra-bar updates.

### Look-ahead-bias avoidance
- Compute EMA/ADX/RV using only the **close of the current day and prior days**.
- Do not use the current day’s high/low for regime assignment; use `close`.
- If volume is delayed or adjusted after the close, stamp the regime with the **next-day open timestamp** or use the prior day’s volume ratio.

---

## (b) HMM Regime Detector

### Source guidance
- Prompt instruction: *2–3 state Gaussian on daily log returns, trailing 10y fit, forward-only inference.*
- Wiki: `entities/hidden-markov-models-kalman-filter-demystified.md` and `concepts/time-series.md` describe HMM as a discrete state-space model using forward (predictive) pass + correction/update, equivalent to the sum-product/Viterbi algorithm.

### Inputs
| Input | Symbol | Transform |
|-------|--------|-----------|
| Daily close | `C_t` | `r_t = ln(C_t / C_{t-1})` |
| Optional realized volatility | `RV_t` | NOT SPECIFIED, propose default 21-day intraday RV if available |

### Parameters
| Parameter | Value / default | Note |
|-----------|-----------------|------|
| Number of states | `K = 3` | Prompt says 2–3; **propose 3** (low-vol, high-vol/trend, stress/reversal). |
| Observation distribution | Diagonal Gaussian | Wiki references `impl_diagonal_gaussian_hmm` in graph.json; covariance per state is diagonal. |
| Input feature | Daily log returns | Prompt-specified. NOT SPECIFIED whether to include squared returns or RV; propose default: log returns only. |
| Training window | 10 years = ~2,520 trading days | Prompt-specified trailing window. |
| Refit frequency | NOT SPECIFIED, propose default **quarterly (63 trading days)** or **expanding annually** | Forward-only refit must use only data available up to the refit date. |
| EM iterations | NOT SPECIFIED, propose default `max_iter=100`, `tol=1e-4` | Use `hmmlearn` or `pomegranate` with random init over 10 seeds. |
| Smoothing / decoding | Forward-only filtered state probability | Use `model.predict_proba(X)` at each step; do **not** run full Viterbi on the entire history for the current label. |
| State persistence prior | NOT SPECIFIED | Propose default `min_covar=1e-3` and left-to-right transition prior if desired. |

### Pandas pseudocode
```python
from hmmlearn.hmm import GaussianHMM
import pandas as pd
import numpy as np

def hmm_regime(df: pd.DataFrame,
               n_states: int = 3,
               train_days: int = 2520,
               refit_days: int = 63,
               seed: int = 42) -> pd.DataFrame:
    """
    Forward-only HMM regime detector.
    Returns columns: state, state_prob, low_vol_prob, mid_vol_prob, high_vol_prob
    """
    close = df['close']
    r = np.log(close / close.shift(1)).dropna().to_frame('ret')

    out = pd.DataFrame(index=df.index)
    states = pd.Series(index=df.index, dtype='Int64')
    probs = pd.DataFrame(index=df.index,
                         columns=[f'state_{k}_prob' for k in range(n_states)],
                         dtype=float)

    last_fit_idx = -1
    model = None

    for i in range(train_days, len(df)):
        if model is None or (i - last_fit_idx) >= refit_days:
            # --- look-ahead-bias guard ---
            # Fit only on the trailing 10-year window ending *yesterday*.
            train_slice = r.iloc[i - train_days : i]
            model = GaussianHMM(
                n_components=n_states,
                covariance_type='diag',
                n_iter=100,
                random_state=seed,
                init_params='stmc'   # start prob, trans, means, covars
            )
            # Optional: sort states by mean return after fitting for stable labels
            model.fit(train_slice.values)
            last_fit_idx = i

        # Forward-only inference on today's return
        x = r.iloc[i:i+1].values
        prob_t = model.predict_proba(x)[0]
        state_t = int(np.argmax(prob_t))

        states.iloc[i] = state_t
        probs.iloc[i] = prob_t

    out['hmm_state'] = states
    out['hmm_state_prob'] = probs.max(axis=1)
    out = pd.concat([out, probs], axis=1)
    return out
```

### Output states
| State | Interpretation (post-fit labeling) |
|-------|------------------------------------|
| 0 | Low-volatility / ranging |
| 1 | Trending / moderate-volatility |
| 2 | High-volatility / stress / reversal |

**State labels must be re-sorted after each refit** so that state 0/1/2 keep a consistent economic meaning (e.g., sort by mean return or variance).

### Update frequency
Daily, after the close. The model is refit every `refit_days` using only trailing data; inference is run one day at a time.

### Look-ahead-bias avoidance
1. **Trailing window:** fit window ends strictly before the inference day.
2. **Refit on schedule, not on performance:** do not refit because of a recent regime change; use a fixed calendar.
3. **Forward-only decoding:** use filtered probabilities (`predict_proba`), not smoothed probabilities that use future observations.
4. **No future returns in feature engineering:** do not include forward-looking volatility or centered moving averages.

### Known pitfalls (from wiki)
- EM can be unstable on financial returns; run multiple random starts and keep the highest-likelihood fit.
- Gaussian assumption conflicts with fat tails; robust extensions (Student-t HMM, particle filter) are mentioned but not specced.
- State labels are not identifiable across refits; sort by mean/variance each time.
- A 10-year window may miss rare crisis regimes; consider an expanding window or a shorter window with shrinkage.

---

## (c) ADX Momentum-Exhaustion Regime Detector

### Source logic
- `concepts/momentum-exhaustion-adx-reversion.md`
- `entities/ssrn-6454659.md`
- ADX length / threshold anchored to `strategies/pine/te_v9_1_CORE.pine` and `TE_v9.4_ADX_GATE_SplitHalf.pine`

### Inputs
| Input | Symbol | Note |
|-------|--------|------|
| Close | `close` | Daily close |
| High | `high` | Daily high |
| Low | `low` | Daily low |
| VWAP (optional) | `vwap` | Wiki uses VWAP as fair-value anchor; exact formula NOT SPECIFIED. Propose default: daily VWAP = Σ(price × volume) / Σ(volume). |

### Parameters
| Parameter | Source value / proposed default | Note |
|-----------|---------------------------------|------|
| ADX length | **14** | Exact from Pine. |
| Low-ADX regime | NOT SPECIFIED, propose default `< 18` | v9.1 uses 18 as the minimum trend-strength gate. |
| Moderate-ADX regime | NOT SPECIFIED, propose default `[18, 25)` | Boundary inferred from v9.4 threshold (20) plus headroom. |
| High-ADX / exhaustion regime | NOT SPECIFIED, propose default `≥ 25` | Wiki describes "high ADX (trend exhaustion)". |
| VWAP deviation threshold | NOT SPECIFIED, propose default **2 × ATR14** | Wiki says "price far from VWAP"; no exact multiplier given. |

### Regime mapping (from wiki)
| ADX level | Wiki interpretation | Strategy bias |
|-----------|---------------------|---------------|
| Low (`< 18`) | Weak/no trend; momentum signals have low predictive power; reversal signals work best | Mean-reversion |
| Moderate (`18–25`) | Developing trend; momentum signals dominate | Momentum/trend-following |
| High (`≥ 25`) | Trend exhaustion; momentum fades; reversal signals for exhaustion become profitable | Reversion / de-risk |

### Pandas pseudocode
```python
import pandas as pd
import numpy as np

def adx_exhaustion_regime(df: pd.DataFrame,
                          adx_len: int = 14,
                          low_thresh: float = 18.0,
                          high_thresh: float = 25.0,
                          use_vwap: bool = False,
                          vwap_dev_atr_mult: float = 2.0) -> pd.Series:
    """
    Returns one of: 'low_adx_reversion', 'moderate_adx_momentum',
                    'high_adx_exhaustion', 'vwap_extreme_exhaustion'
    """
    close = df['close']
    # ADX via pandas-ta with exact length 14
    adx = df.ta.adx(length=adx_len)['ADX_' + str(adx_len)]

    atr = df.ta.atr(length=adx_len)['ATRr_' + str(adx_len)]

    regime = pd.Series('moderate_adx_momentum', index=df.index)
    regime.loc[adx < low_thresh] = 'low_adx_reversion'
    regime.loc[adx >= high_thresh] = 'high_adx_exhaustion'

    if use_vwap:
        vwap = df.get('vwap')
        if vwap is None:
            # Typical price proxy if VWAP not supplied
            typical = (df['high'] + df['low'] + df['close']) / 3.0
            vwap = (typical * df['volume']).cumsum() / df['volume'].cumsum()
        dev = (close - vwap).abs() / atr
        extreme = (adx >= high_thresh) & (dev >= vwap_dev_atr_mult)
        regime.loc[extreme] = 'vwap_extreme_exhaustion'

    return regime
```

### Output states
- `low_adx_reversion` — choppy / no-trend environment; favor mean-reversion.
- `moderate_adx_momentum` — developing trend; favor momentum / trend-following.
- `high_adx_exhaustion` — strong trend may be exhausted; reduce trend exposure.
- `vwap_extreme_exhaustion` — high ADX plus large VWAP deviation; strongest reversal cue (only if VWAP is supplied).

### Update frequency
Daily after close.

### Look-ahead-bias avoidance
- ADX14 uses only current and past high/low/close (Wilder smoothing is causal).
- VWAP must be computed **cumulatively from the start of the current session/period**; do not use future bars. For daily macro use, supply a pre-computed daily VWAP or use a rolling anchored VWAP.
- Do not optimize the 18/25 thresholds on the same data used for signal evaluation; calibrate on a held-out period or use the Pine-provided 18/20 values.

### Known pitfalls (from wiki)
- Optimal ADX thresholds are market-specific and time-varying; fixed thresholds may degrade.
- High-ADX periods coincide with high volume and wider spreads, increasing implementation shortfall.
- Combining ADX with VWAP requires a causal VWAP calculation; end-of-day VWAP can be revised post-close.

---

## Appendix — Wiki methods that could NOT be numerically specced

| Method | Source | Why it is omitted |
|--------|--------|-------------------|
| Clustering detector | `graph.json` node `clustering_detector`; source file `comparisons/regime-detector-comparison.md` **missing** | No input features, distance metric, number of clusters, or update rule in repo. |
| Bayesian smoothing detector | `graph.json` node `bayesian_smoothing_detector`; source file **missing** | No prior, likelihood, state space, or smoothing window in repo. |
| HLPPL bubble detector | `entities/hlppl-bubble-model.md`, `concepts/hlppl-model.md` | Has LPPL formula `ln p(t) = A + B(t_c − t)^m + C(t_c − t)^m cos(ω ln(t_c − t) + φ)`, but the seven parameters (`A, B, C, t_c, m, ω, φ`) and behavioral inputs (Hype Index, Sentiment Score, transformer weights) are **not specified numerically**; also criticized as prone to in-sample overfitting. |
| Kalman filter trend detector | `concepts/kalman-filter-finance.md` | State dimension, transition/measurement matrices, and noise covariances are **not specified**. |

---

## Revision note
If the missing comparison files (`regime-detector-comparison.md`, `structural-vs-statistical.md`) are later restored to `unified-wiki/`, this spec should be updated to extract the clustering and Bayesian smoothing parameters verbatim.
