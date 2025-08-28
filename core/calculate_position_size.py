def position_size_usd_fixed_risk(price: float, atr: float, risk_usd: float, sl_mult: float):
    """Simple position size: risk_usd / (SL distance).
    SL distance ≈ atr * sl_mult. Assumes 1x USD contract (spot notionals).
    """
    if atr is None or atr <= 0:
        return 0.0
    sl_dist = atr * sl_mult
    if sl_dist <= 0:
        return 0.0
    qty = risk_usd / sl_dist / price
    return max(qty, 0.0)
