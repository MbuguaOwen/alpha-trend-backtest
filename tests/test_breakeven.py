from backtest.core.trade_manager import TradeManager, ExitParams

def test_be_trigger():
    tm = TradeManager(ExitParams(atr_mult_sl=10, atr_mult_tp=20, breakeven_progress=0.5, tsl_step_atr_mult=5))
    tm.open("t0","LONG",100, atr=2, qty=1.0)
    # progress to BE threshold
    # atr=2 -> tp_dist=40 -> half progress = +20
    # bar drives to 121 high, close 121
    done = tm.on_bar("t1", high=121, low=100, close=121, atr=2)
    assert tm.active is not None
    assert tm.active.be_moved is True
    assert tm.active.sl == 100
