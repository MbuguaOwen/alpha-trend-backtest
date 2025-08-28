from collections import deque

class PullbackResumption:
    """Simplified entry: In UP regime, require a pullback (price below MA) then close back above.
    In DOWN regime, inverse. Parameters:
      - ma_lookback
      - pullback_frac (0..1) : minimum pullback below/above MA as a fraction of ATR or MA (here MA)
    This is a placeholder; live engine should be imported via adapters for parity.
    """
    def __init__(self, ma_lookback: int = 20, pullback_frac: float = 0.002):
        self.lookback = ma_lookback
        self.buf = deque(maxlen=ma_lookback)
        self.pullback_seen = False

    def update_ma(self, price: float):
        self.buf.append(price)
        if len(self.buf) < self.lookback:
            return None
        return sum(self.buf)/len(self.buf)

    def on_bar(self, price: float, regime: str):
        ma = self.update_ma(price)
        if ma is None or regime == "FLAT":
            self.pullback_seen = False
            return None
        if regime == "UP":
            if price < ma:
                self.pullback_seen = True
                return None
            if self.pullback_seen and price >= ma:
                self.pullback_seen = False
                return "LONG"
        elif regime == "DOWN":
            if price > ma:
                self.pullback_seen = True
                return None
            if self.pullback_seen and price <= ma:
                self.pullback_seen = False
                return "SHORT"
        return None
