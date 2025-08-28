from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from .data_loader import iter_symbol_bars
from .adapters import load_regime_classifier, load_signal_engine, load_trade_manager, load_atr, load_position_sizer
from .reporting import summarize_trades
from .atr import ATR
from tqdm.auto import tqdm

def _to_epoch_iso(iso: Optional[str | int | float]) -> Optional[int]:
    if iso is None:
        return None
    s = str(iso).strip()
    if s.isdigit():
        v = int(s)
        return v // 1000 if v > 1_000_000_000_0 else v
    dt = datetime.fromisoformat(s.replace("Z", ""))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def run_symbol(
    symbol: str,
    data_root: Path,
    start: Optional[str],
    end: Optional[str],
    cfg: dict,
    outputs_dir: Path,
    logger,
    progress: bool = False,
):
    # Instantiate engines (fallback or live)
    reg_mod, reg_fb = load_regime_classifier()
    sig_mod, sig_fb = load_signal_engine()
    tm_mod, tm_fb = load_trade_manager()
    atr_mod, atr_fb = load_atr()
    pos_mod, pos_fb = load_position_sizer()

    # Params from YAML
    reg_cfg = cfg.get("regime", {}).get("slope", {"n_short": 30, "n_long": 120})
    sig_cfg = cfg.get("entry", {}).get("pullback_resumption", {"ma_lookback": 20})
    exit_cfg = cfg.get("exits", {}).get(symbol, {})
    risk_cfg = cfg.get("risk", {}).get(symbol, {"risk_usd": 1.0})

    # Build components (use attribute/class names from fallbacks)
    regime = reg_mod.SlopeRegime(**reg_cfg)
    signal = sig_mod.PullbackResumption(**sig_cfg)
    exit_params = tm_mod.ExitParams(
        atr_mult_sl = exit_cfg.get("sl_mult", 15.0),
        atr_mult_tp = exit_cfg.get("tp_mult", 60.0),
        breakeven_progress = exit_cfg.get("breakeven_progress", 0.5),
        tsl_step_atr_mult = exit_cfg.get("tsl_step_atr_mult", 3.0),
    )
    tm = tm_mod.TradeManager(exit_params)
    atr = ATR(period=exit_cfg.get("atr_period", 14))
    risk_usd = risk_cfg.get("risk_usd", 1.0)
    sl_mult = exit_cfg.get("sl_mult", 15.0)

    trades: List[Dict[str, Any]] = []
    timeline_rows: List[str] = []
    timeline_header = "timestamp,open,high,low,close,atr,regime,signal,position,sl,tp\n"
    timeline_rows.append(timeline_header)

    def write_trade(t):
        trades.append({
            "symbol": symbol,
            "entry_ts": t.entry_ts,
            "entry_price": t.entry_price,
            "side": t.side,
            "sl": t.sl,
            "tp": t.tp,
            "exit_ts": t.exit_ts,
            "exit_price": t.exit_price,
            "exit_reason": t.exit_reason,
            "R": t.R,
            "size": t.size,
        })

    # Progress bar setup (per-bar)
    start_ep = _to_epoch_iso(start) if start else None
    end_ep = _to_epoch_iso(end) if end else None
    total_bars: Optional[int] = None
    if start_ep is not None and end_ep is not None:
        total_bars = max(0, (end_ep - start_ep) // 60)
    pbar = tqdm(
        total=total_bars,
        desc=f"{symbol} bars",
        unit="bar",
        leave=False,
        dynamic_ncols=True,
        disable=not progress,
        mininterval=0.2,
        smoothing=0.1,
    )

    for bar in iter_symbol_bars(Path(data_root), symbol, start, end):
        ts = bar["timestamp"]; o=bar["open"]; h=bar["high"]; l=bar["low"]; c=bar["close"]
        cur_atr = atr.update(o,h,l,c)
        reg = regime.update(c)
        sig = None
        pos = "FLAT" if tm.active is None else tm.active.side

        # Generate entries only if flat and we have ATR
        if tm.active is None and cur_atr is not None:
            sig = signal.on_bar(c, reg)
            if sig in ("LONG","SHORT") and reg in ("UP","DOWN"):
                qty = 0.0
                # simple sizing
                sl_dist = cur_atr * sl_mult
                if sl_dist > 0 and c > 0:
                    qty = risk_usd / sl_dist / c
                t = tm.open(ts, sig, c, cur_atr, qty)
        else:
            # advance trade
            done = tm.on_bar(ts, h, l, c, cur_atr or 0.0)
            if done:
                write_trade(done)
                pos = "FLAT"

        timeline_rows.append(f"{ts},{o},{h},{l},{c},{cur_atr or ''},{reg},{sig or ''},{pos},{tm.active.sl if tm.active else ''},{tm.active.tp if tm.active else ''}\n")
        pbar.update(1)

    pbar.close()

    # If trade still open, force-close at last price as BE
    if tm.active is not None:
        t = tm.active
        t.exit_ts = ts; t.exit_price = c; t.exit_reason = "BE"; t.R = 0.0
        write_trade(t)
        tm.active = None

    # Write artifacts
    outdir = outputs_dir / "backtest"
    outdir.mkdir(parents=True, exist_ok=True)
    # trades CSV
    trades_csv = outdir / f"{symbol}_trades.csv"
    if trades:
        import csv
        with open(trades_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
            w.writeheader()
            for r in trades:
                w.writerow(r)
    # timeline CSV
    with open(outdir / f"{symbol}_timeline.csv", "w", encoding="utf-8") as f:
        f.writelines(timeline_rows)

    # Summary
    summary = summarize_trades(trades)
    return summary
