import argparse, os, json
from pathlib import Path
from datetime import datetime
from backtest.core.config_loader import load_config, deep_update
from backtest.core.logger import setup_logger
from backtest.core.walkforward import parse_wf, WFSpec, build_wf_windows
from backtest.core.backtest_engine import run_symbol
from backtest.core.reporting import write_json

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, help="Path to YAML config.")
    p.add_argument("--mode", choices=["insample","oos","walkforward"], help="Override backtest.mode.")
    p.add_argument("--oos_last_k_months", type=int, help="Override YAML OOS months.")
    p.add_argument("--walkforward", help='Override YAML walkforward e.g. "train=3,test=1,step=1"')
    p.add_argument("--symbols", help="Filter symbols: comma-separated.")
    p.add_argument("--start", help="Start ISO timestamp (UTC). e.g. 2025-01-01T00:00:00")
    p.add_argument("--end", help="End ISO timestamp (UTC). e.g. 2025-07-01T00:00:00")
    p.add_argument("--data-root", dest="data_root", help="Path to data root.")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()

def main():
    args = parse_args()
    cfg = load_config(args.config)

    # Override via CLI
    overrides = {"backtest": {}}
    if args.mode:
        overrides["backtest"]["mode"] = args.mode
    if args.oos_last_k_months is not None:
        overrides["backtest"]["oos_last_k_months"] = args.oos_last_k_months
    if args.walkforward:
        wf = parse_wf(args.walkforward)
        overrides["backtest"]["walkforward"] = {"train_months": wf.train_months, "test_months": wf.test_months, "step_months": wf.step_months}
        overrides["backtest"]["mode"] = "walkforward"
    if args.data_root:
        overrides["paths"] = {"data_root": args.data_root}
    cfg = deep_update(cfg, overrides)

    mode = cfg.get("backtest", {}).get("mode", "insample")
    data_root = Path(cfg.get("paths", {}).get("data_root", "data"))
    outputs_dir = Path(cfg.get("paths", {}).get("outputs_dir", "outputs"))
    symbols = cfg.get("symbols", ["BTCUSDT","ETHUSDT","SOLUSDT"])
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    outputs_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(str(outputs_dir / "logs/backtest.log"))

    logger.info("=== BACKTEST RUN START ===")
    logger.info(f"mode={mode} symbols={symbols} data_root={data_root} start={args.start} end={args.end}")
    if os.environ.get("LIVE_ENGINE_PACKAGE"):
        logger.info(f"LIVE_ENGINE_PACKAGE={os.environ['LIVE_ENGINE_PACKAGE']}")

    summaries = {}
    if mode == "insample" or mode == "oos":
        # For OOS we simply restrict to last K months in the provided [start,end] or data extent (left to user)
        for sym in symbols:
            summaries[sym] = run_symbol(sym, data_root, args.start, args.end, cfg, outputs_dir, logger)
    elif mode == "walkforward":
        wf_cfg = cfg["backtest"]["walkforward"]
        wf = WFSpec(**wf_cfg)
        if not args.start or not args.end:
            logger.warning("walkforward requires --start and --end for deterministic windows. Proceeding may yield empty runs.")
        windows = build_wf_windows(args.start or "2025-01-01T00:00:00", args.end or "2025-08-01T00:00:00", wf)
        fold_idx = 0
        for train_s, train_e, test_s, test_e in windows:
            logger.info(f"WALKFORWARD fold={fold_idx} train=[{train_s}..{train_e}) test=[{test_s}..{test_e})")
            for sym in symbols:
                # Evaluate only on test window (no parameter fitting here since YAML-first)
                k = f"{sym}/fold_{fold_idx}"
                summaries[k] = run_symbol(sym, data_root, test_s, test_e, cfg, outputs_dir, logger)
            fold_idx += 1

    # Write global summary JSON
    write_json(outputs_dir / "backtest/summary.json", summaries)
    logger.info("=== BACKTEST RUN DONE ===")
    print(json.dumps(summaries, indent=2))

if __name__ == "__main__":
    main()
