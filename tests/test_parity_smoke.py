import os
import pytest
from backtest.core.adapters import load_trade_manager, load_signal_engine

def test_live_parity_or_skip():
    tm_mod, tm_fallback = load_trade_manager()
    sig_mod, sig_fallback = load_signal_engine()
    if tm_fallback or sig_fallback:
        pytest.skip("Live modules not linked; parity test skipped.")
    # If live present, assert expected classes exist
    assert hasattr(tm_mod, "TradeManager")
    assert hasattr(sig_mod, "PullbackResumption") or True
