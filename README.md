# Backtest Mirror — 1:1 with Live Engine (YAML-first)

**Goal:** Provide a production-grade backtest harness that **imports your live modules** (regime, signal, trade management, sizing) for **true logic parity**. If live modules are not on `PYTHONPATH`, the harness will **fallback** to local stubs so you can smoke-test the pipeline. For real analysis, link your live engine.

---

## 0) Scope & Parity

- Imports the **exact** live modules when available via `LIVE_ENGINE_PACKAGE` (e.g. `tsmom_eventwave_engine.core`).  
- YAML-first, no hard-coded thresholds.  
- One-bar-at-a-time, **no look-ahead**, strict event order.  
- Symbols & params read **only** from YAML.

## 1) Config

See `configs/default.yaml`. Includes the requested block:

```yaml
backtest:
  mode: "walkforward"     # "insample" | "oos" | "walkforward"
  oos_last_k_months: 2
  walkforward:
    train_months: 3
    test_months: 1
    step_months: 1
```

## 2) CLI

`run_backtest.py` supports:

```
--config CONFIG
--mode {insample,oos,walkforward}
--oos_last_k_months INT
--walkforward "train=3,test=1,step=1"
--symbols BTCUSDT,ETHUSDT,SOLUSDT
--start YYYY-MM-DDTHH:MM:SS
--end   YYYY-MM-DDTHH:MM:SS
--data-root PATH
--workers INT
--seed INT
--dry-run
```

**Examples**

```bash
python -m run_backtest --config configs/default.yaml
python -m run_backtest --config configs/default.yaml --mode oos --oos_last_k_months 2
python -m run_backtest --config configs/default.yaml --mode walkforward --walkforward "train=3,test=1,step=1" --start 2025-01-01T00:00:00 --end 2025-08-01T00:00:00
# PowerShell quoting works with the same double quotes:
python -m run_backtest --config configs/default.yaml --mode walkforward --walkforward "train=3,test=1,step=1"
```

## 3) Data Layer

- Input: **1-minute OHLCV CSVs** (UTC).  
- Path: `data/<SYMBOL>/*.csv`.  
- Columns: `timestamp,open,high,low,close,volume`.  
- Thin CSV adapter implemented; Parquet can be added without changing the candle iterator semantics.

## 4) Metrics & Artifacts

Per symbol:
- `trades` count, exit breakdown **SL/BE/TSL**  
- `win_rate, avg_R, median_R, sum_R`  
- Stability ratio **G = (TSL + BE) / |SL|**

Artifacts:
- `outputs/backtest/<symbol>_trades.csv`  
- `outputs/backtest/<symbol>_timeline.csv` (bar-level trace)  
- `outputs/backtest/summary.json` (global consolidated report)

## 5) Exit Logic Parity

Exit logic is **delegated** to your live `TradeManager` when `LIVE_ENGINE_PACKAGE` is set.  
If not present, a faithful fallback provides ATR-scaled SL/TP, **breakeven** at configured progress, and **TSL** stepping. Use live modules for real runs.

## 6) Regime & Entry Parity

Regime & entry are **delegated** to your live modules when linked. Fallbacks include:  
- `SlopeRegime` (short/long MA cross proxy)  
- `PullbackResumption` (simple pullback-then-resume proxy)

## 7) Reporting & Logging

Logs are written to `outputs/logs/backtest.log`.  
Run header prints parsed config, bounds, symbol list, and mode.

## 8) Tests

- `test_atr.py` — deterministic ATR smoke.  
- `test_breakeven.py`, `test_tsl.py` — BE/TSL progression on scripted path.  
- `test_parity_smoke.py` — **skips** if live modules are not linked; otherwise asserts basic presence.

## 9) Structure (deliverable)

```
run_backtest.py
backtest/
  __init__.py
  core/
    __init__.py
    adapters.py
    atr.py
    backtest_engine.py
    calculate_position_size.py
    config_loader.py
    data_loader.py
    logger.py
    regime_classifier.py       # fallback stub
    reporting.py
    signal_engine.py           # fallback stub
    trade_manager.py           # fallback stub
    walkforward.py
configs/
  default.yaml
tests/
  __init__.py
  conftest.py
  test_atr.py
  test_breakeven.py
  test_tsl.py
  test_parity_smoke.py
  test_walkforward_parser.py
  fixtures/
    mini_prices.csv
README.md
```

## 10) How to link your live engine for **true parity**

1. Install your live package in the same venv, or add it to `PYTHONPATH`.  
2. Export the package root so adapters can import your modules:

```bash
export LIVE_ENGINE_PACKAGE=tsmom_eventwave_engine.core
# or whatever your live package root is
```

3. Re-run the backtest commands. Parity test will no longer skip.

---

### Notes

- Times are treated as **UTC**. Show local times only in external reports if desired.  
- All thresholds & behavior derive from YAML.  
- Walkforward uses sliding month windows with your `train/test/step` schedule. No parameter fitting is performed; it simply evaluates per test window using YAML params (consistent with “YAML-first”).  
- Distribution plots are intentionally optional to keep runtime light; you can add them in `reporting.py` if needed.
