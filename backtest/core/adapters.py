"""
Adapters that import *live* engine modules for perfect parity.
If live modules are not available, we fall back to local stubs that
mirror the expected interfaces. Set the environment variable:

  LIVE_ENGINE_PACKAGE=tsmom_eventwave_engine.core

…or another package path where your live modules reside.
"""
import importlib
import os

FALLBACK_NOTE = " (using fallback stub — link your live engine for true parity)"

def _try_import(modname):
    try:
        return importlib.import_module(modname)
    except Exception:
        return None

def _load(mod_basename):
    pkg = os.environ.get("LIVE_ENGINE_PACKAGE", "").strip()
    if pkg:
        m = _try_import(f"{pkg}.{mod_basename}")
        if m:
            return m, False
    # Try some common guesses
    for guess in ["tsmom_eventwave_engine.core", "eventwave.core", "live_engine.core", "core"]:
        m = _try_import(f"{guess}.{mod_basename}")
        if m:
            return m, False
    # Fallback to local stubs
    m = importlib.import_module(f"backtest.core.{mod_basename}")
    return m, True

def load_regime_classifier():
    m, is_fallback = _load("regime_classifier")
    return m, is_fallback

def load_signal_engine():
    m, is_fallback = _load("signal_engine")
    return m, is_fallback

def load_trade_manager():
    m, is_fallback = _load("trade_manager")
    return m, is_fallback

def load_position_sizer():
    m, is_fallback = _load("calculate_position_size")
    return m, is_fallback

def load_atr():
    m, is_fallback = _load("atr")
    return m, is_fallback
