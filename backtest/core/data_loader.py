from pathlib import Path
import csv
from typing import Iterator, Dict, Any, Optional, Iterable
from datetime import datetime, timezone
import re

# --- time helpers ------------------------------------------------------------
def _to_epoch_seconds(ts: Optional[str | int | float]) -> Optional[int]:
    if ts is None:
        return None
    s = str(ts).strip()
    if s.isdigit():
        v = int(s)
        # treat large numbers as milliseconds
        return v // 1000 if v > 1_000_000_000_0 else v
    # ISO 8601 (allow trailing Z)
    try:
        dt = datetime.fromisoformat(s.replace("Z", ""))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception as e:
        raise ValueError(f"Unrecognized timestamp: {ts!r}") from e

def _minute_floor(epoch_s: int) -> int:
    return epoch_s - (epoch_s % 60)

def _iso_minute(epoch_s: int) -> str:
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc).replace(second=0, microsecond=0).isoformat(timespec="seconds")

# --- schema helpers ----------------------------------------------------------
TS_ALIASES: tuple[str, ...] = ("timestamp", "ts", "t", "time")
PRICE_ALIASES: tuple[str, ...] = ("price", "p", "last_price", "close", "c")
QTY_ALIASES: tuple[str, ...] = ("qty", "quantity", "size", "amount", "volume", "q")

def _first_present(row: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
    for k in keys:
        if k in row:
            v = row.get(k)
            if v is not None and str(v).strip() != "":
                return str(v)
    return None

# --- readers -----------------------------------------------------------------
def _iter_ohlcv_file(path: Path) -> Iterator[Dict[str, Any]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # normalize keys to lowercase and strip potential BOM to be permissive
            row_l = { (k.lower().lstrip("\ufeff") if isinstance(k, str) else k): v for k, v in row.items() }
            ep = _to_epoch_seconds(_first_present(row_l, TS_ALIASES))
            yield {
                "timestamp": _iso_minute(ep),
                "open": float(row_l["open"]),
                "high": float(row_l["high"]),
                "low": float(row_l["low"]),
                "close": float(row_l["close"]),
                "volume": float(row_l.get("volume", 0.0)),
            }

def _iter_ticks_aggregated_1m(path: Path) -> Iterator[Dict[str, Any]]:
    """Aggregate trade ticks to 1-minute OHLCV.

    Accepts varied headers and ignores unknown columns.
    - Timestamp aliases: TS_ALIASES
    - Price aliases: PRICE_ALIASES
    - Quantity aliases: QTY_ALIASES (defaults to 0.0 if absent)
    """
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cur_min: Optional[int] = None
        o = h = l = c = None  # type: ignore[assignment]
        vol = 0.0
        for row in reader:
            # normalize keys to lowercase, strip BOM, ignore extras
            row_l: Dict[str, Any] = { (k.lower().lstrip("\ufeff") if isinstance(k, str) else k): v for k, v in row.items() }

            ts_raw = _first_present(row_l, TS_ALIASES)
            if ts_raw is None:
                # no timestamp -> skip row
                continue
            ep = _to_epoch_seconds(ts_raw)
            m = _minute_floor(ep)

            p_raw = _first_present(row_l, PRICE_ALIASES)
            if p_raw is None:
                # no price -> skip row
                continue
            try:
                p = float(p_raw)
            except Exception:
                # bad price -> skip
                continue

            q_raw = _first_present(row_l, QTY_ALIASES)
            try:
                q = float(q_raw) if q_raw is not None else 0.0
            except Exception:
                q = 0.0

            if cur_min is None:
                cur_min = m
                o = h = l = c = p
                vol = q
                continue

            if m != cur_min:
                # flush previous minute
                yield {
                    "timestamp": _iso_minute(cur_min),
                    "open": o, "high": h, "low": l, "close": c, "volume": vol,
                }
                # start new minute
                cur_min = m
                o = h = l = c = p
                vol = q
            else:
                # same minute, update OHLCV
                c = p
                if p > h: h = p
                if p < l: l = p
                vol += q

        # flush last minute
        if cur_min is not None:
            yield {
                "timestamp": _iso_minute(cur_min),
                "open": o, "high": h, "low": l, "close": c, "volume": vol,
            }

def iter_ohlcv_csv(path: Path) -> Iterator[Dict[str, Any]]:
    """Yield bars from either:
       - 1-minute OHLCV CSV: timestamp,open,high,low,close,volume
       - Ticks CSV: timestamp,price/aliases,qty/aliases,[...]

    Detection rules:
    - OHLCV if {open,high,low,close} ⊆ header
    - Ticks if any price-alias ∧ any quantity-alias in header
    - Otherwise raise with raw header line
    """
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    # Read raw header line and also parse into tokens safely
    with open(path, "r", newline="", encoding="utf-8") as f:
        raw_header = (f.readline() or "").strip()
    # parse tokens with csv to honor quotes; also handle BOM on first token
    try:
        tokens = next(csv.reader([raw_header])) if raw_header else []
    except Exception:
        tokens = [c.strip() for c in raw_header.split(",") if c.strip()]
    tokens_l = [t.strip().lower().lstrip("\ufeff") for t in tokens]
    header_set = set(tokens_l)

    # choose reader by schema
    if {"open", "high", "low", "close"}.issubset(header_set):
        yield from _iter_ohlcv_file(path)
    elif (any(p in header_set for p in PRICE_ALIASES) and any(q in header_set for q in QTY_ALIASES)):
        yield from _iter_ticks_aggregated_1m(path)
    else:
        raise ValueError(f"Unrecognized CSV schema in {path.name}: {raw_header}")

 

def _yymm_from_name(name: str):
    m = re.search(r"(\d{4})[-_](\d{2})", name)
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    start = datetime(y, mo, 1, tzinfo=timezone.utc)
    # month end = first day of next month
    if mo == 12:
        end = datetime(y + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(y, mo + 1, 1, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())

def find_symbol_csvs(
    data_root: Path, symbol: str, start: Optional[str], end: Optional[str]
):
    """Return only files that could overlap [start,end)."""
    symdir = data_root / symbol
    files = sorted(symdir.glob("*.csv"))
    import logging
    log = logging.getLogger("backtest")
    if not files:
        log.warning(f"No CSV files found for {symbol} in {symdir}")
        return []

    # If we don't have a window, keep all
    s_ep = _to_epoch_seconds(start) if start else None
    e_ep = _to_epoch_seconds(end) if end else None
    if s_ep is None and e_ep is None:
        log.info(f"{symbol}: {len(files)} CSV files in {symdir}")
        return files

    kept = []
    for fp in files:
        rng = _yymm_from_name(fp.name)
        if rng is None:
            # keep unknown-named files just in case
            kept.append(fp)
            continue
        f_start, f_end = rng
        # overlap if file range intersects [s_ep,e_ep)
        if (e_ep is None or f_start < e_ep) and (s_ep is None or f_end > s_ep):
            kept.append(fp)

    log.info(
        f"{symbol}: using {len(kept)}/{len(files)} CSV files (window filter) in {symdir}"
    )
    return kept

def iter_symbol_bars(data_root: Path, symbol: str, start: Optional[str], end: Optional[str]):
    start_ep = _to_epoch_seconds(start) if start else None
    end_ep = _to_epoch_seconds(end) if end else None
    for fp in find_symbol_csvs(data_root, symbol, start, end):
        for bar in iter_ohlcv_csv(fp):
            ts_ep = _to_epoch_seconds(bar["timestamp"])
            if start_ep is not None and ts_ep < start_ep:
                continue
            if end_ep is not None and ts_ep >= end_ep:
                continue
            yield bar
