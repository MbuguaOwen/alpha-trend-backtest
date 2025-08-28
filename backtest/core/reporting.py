import json
from pathlib import Path
from statistics import mean, median

def summarize_trades(trades):
    exits = {"SL":0, "BE":0, "TSL":0}
    Rs = []
    for t in trades:
        exits[t.get("exit_reason","SL")] = exits.get(t.get("exit_reason","SL"), 0) + 1
        Rs.append(t.get("R", 0.0))
    win_rate = (exits.get("TSL",0) + exits.get("BE",0)) / max(1, sum(exits.values()))
    avg_R = mean(Rs) if Rs else 0.0
    med_R = median(Rs) if Rs else 0.0
    sum_R = sum(Rs) if Rs else 0.0
    G = (exits.get("TSL",0) + exits.get("BE",0)) / max(1, exits.get("SL",0))
    return {
        "trades": len(trades),
        "exits": exits,
        "win_rate": win_rate,
        "avg_R": avg_R,
        "median_R": med_R,
        "sum_R": sum_R,
        "G": G,
    }

def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
