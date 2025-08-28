from collections import deque

class ATR:
    """Simple ATR with Wilder smoothing."""
    def __init__(self, period: int = 14):
        self.period = period
        self.trs = deque(maxlen=period)
        self.prev_close = None
        self._atr = None

    @staticmethod
    def _tr(o, h, l, c_prev):
        if c_prev is None:
            return h - l
        return max(h - l, abs(h - c_prev), abs(l - c_prev))

    def update(self, o, h, l, c):
        tr = self._tr(o, h, l, self.prev_close)
        self.prev_close = c
        if self._atr is None:
            self.trs.append(tr)
            if len(self.trs) == self.period:
                self._atr = sum(self.trs) / self.period
        else:
            self._atr = (self._atr * (self.period - 1) + tr) / self.period
        return self.value

    @property
    def value(self):
        if self._atr is None:
            return None
        return self._atr
