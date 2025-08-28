from backtest.core.trade_manager import TradeManager, ExitParams

def test_tsl_progression():
    tm = TradeManager(ExitParams(atr_mult_sl=10, atr_mult_tp=20, breakeven_progress=0.5, tsl_step_atr_mult=2))
    tm.open("t0","LONG",100, atr=2, qty=1.0)
    # move to BE
    tm.on_bar("t1", high=121, low=100, close=121, atr=2)
    # now each 2*ATR = 4 up should trail
    tm.on_bar("t2", high=130, low=120, close=125, atr=2)
    assert tm.active.tsl_active is True
    assert tm.active.sl >= 121 - 4  # crude check
