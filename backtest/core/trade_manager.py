from dataclasses import dataclass, field

@dataclass
class Trade:
    side: str               # LONG or SHORT
    entry_ts: str
    entry_price: float
    sl: float
    tp: float
    size: float             # qty (in base)
    be_moved: bool = False
    tsl_active: bool = False
    tsl_step: float = 0.0
    exit_ts: str = ""
    exit_price: float = 0.0
    exit_reason: str = ""  # SL | BE | TSL
    R: float = 0.0

@dataclass
class ExitParams:
    atr_mult_sl: float = 15.0
    atr_mult_tp: float = 60.0
    breakeven_progress: float = 0.5  # 0..1 fraction toward TP
    tsl_step_atr_mult: float = 3.0   # move TSL every N*ATR in favorable direction

class TradeManager:
    def __init__(self, exit_params: ExitParams):
        self.p = exit_params
        self.active: Trade | None = None

    def open(self, ts: str, side: str, price: float, atr: float, qty: float):
        sl_dist = self.p.atr_mult_sl * atr
        tp_dist = self.p.atr_mult_tp * atr
        if side == "LONG":
            sl = price - sl_dist
            tp = price + tp_dist
        else:
            sl = price + sl_dist
            tp = price - tp_dist
        self.active = Trade(side=side, entry_ts=ts, entry_price=price, sl=sl, tp=tp, size=qty)
        return self.active

    def _progress(self, price: float, t: Trade):
        if t.side == "LONG":
            return (price - t.entry_price) / (t.tp - t.entry_price) if (t.tp - t.entry_price) > 0 else 0.0
        else:
            return (t.entry_price - price) / (t.entry_price - t.tp) if (t.entry_price - t.tp) > 0 else 0.0

    def on_bar(self, ts: str, high: float, low: float, close: float, atr: float):
        t = self.active
        if not t:
            return None
        # Exit checks — SL, then TP (using existing stops before updates)
        if t.side == "LONG":
            if low <= t.sl:
                t.exit_ts, t.exit_price, t.exit_reason = ts, t.sl, "SL" if not t.tsl_active else "TSL"
            elif high >= t.tp:
                t.exit_ts, t.exit_price, t.exit_reason = ts, t.tp, "TSL"
        else:
            if high >= t.sl:
                t.exit_ts, t.exit_price, t.exit_reason = ts, t.sl, "SL" if not t.tsl_active else "TSL"
            elif low <= t.tp:
                t.exit_ts, t.exit_price, t.exit_reason = ts, t.tp, "TSL"

        if t.exit_reason:
            sl_dist_abs = abs(self.p.atr_mult_sl * atr)
            if t.side == "LONG":
                t.R = (t.exit_price - t.entry_price) / sl_dist_abs
            else:
                t.R = (t.entry_price - t.exit_price) / sl_dist_abs
            done = t
            self.active = None
            return done

        # TSL stepping (simple step every tsl_step_atr_mult ATRs)
        if t.be_moved:
            if t.side == "LONG":
                target = t.entry_price + self.p.tsl_step_atr_mult * atr
                if close >= target:
                    t.tsl_active = True
                    t.sl = max(t.sl, close - self.p.tsl_step_atr_mult * atr)
            else:
                target = t.entry_price - self.p.tsl_step_atr_mult * atr
                if close <= target:
                    t.tsl_active = True
                    t.sl = min(t.sl, close + self.p.tsl_step_atr_mult * atr)

        # Breakeven move
        if not t.be_moved:
            prog = self._progress(close, t)
            if prog >= self.p.breakeven_progress:
                t.be_moved = True
                t.sl = t.entry_price

        return None
