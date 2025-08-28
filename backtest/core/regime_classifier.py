from collections import deque

class SlopeRegime:
    """Very simple slope-based regime: up if MA(close, n_short) > MA(close, n_long)."""
    def __init__(self, n_short: int = 30, n_long: int = 120):
        self.n_short = n_short
        self.n_long = n_long
        self.buf_s = deque(maxlen=n_short)
        self.buf_l = deque(maxlen=n_long)
        self._regime = "FLAT"

    def update(self, price: float):
        self.buf_s.append(price)
        self.buf_l.append(price)
        if len(self.buf_l) < self.n_long:
            self._regime = "FLAT"
            return self._regime
        ma_s = sum(self.buf_s) / len(self.buf_s)
        ma_l = sum(self.buf_l) / len(self.buf_l)
        if ma_s > ma_l:
            self._regime = "UP"
        elif ma_s < ma_l:
            self._regime = "DOWN"
        else:
            self._regime = "FLAT"
        return self._regime

    @property
    def regime(self):
        return self._regime
