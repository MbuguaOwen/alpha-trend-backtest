from pathlib import Path
import csv
from typing import Iterator, Dict, Any, Optional

def iter_ohlcv_csv(path: Path) -> Iterator[Dict[str, Any]]:
    """Yield bars from a 1-minute OHLCV CSV with headers:
    timestamp (UTC ISO or epoch seconds), open, high, low, close, volume
    """
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row.get("timestamp") or row.get("ts")
            yield {
                "timestamp": ts,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0.0)),
            }

def find_symbol_csvs(data_root: Path, symbol: str):
    """Find all CSV files under data_root/<symbol>/*.csv, sorted by name."""
    symdir = data_root / symbol
    return sorted(symdir.glob("*.csv"))

def iter_symbol_bars(data_root: Path, symbol: str, start: Optional[str], end: Optional[str]):
    for fp in find_symbol_csvs(data_root, symbol):
        for bar in iter_ohlcv_csv(fp):
            ts = bar["timestamp"]
            # Simple lexical check supports both iso and epoch as strings
            if start and ts < start:
                continue
            if end and ts >= end:
                continue
            yield bar
