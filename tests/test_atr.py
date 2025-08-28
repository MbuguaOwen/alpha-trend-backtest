from backtest.core.atr import ATR

def test_atr_basic_sequence():
    atr = ATR(period=3)
    data = [
        (1,2,0,1.5),
        (1.5,2.5,1.0,2.0),
        (2.0,3.0,1.5,2.5),
        (2.5,3.5,2.0,3.0),
    ]
    vals = []
    for o,h,l,c in data:
        vals.append(atr.update(o,h,l,c))
    assert vals[-1] is not None
    assert vals[-1] > 0
