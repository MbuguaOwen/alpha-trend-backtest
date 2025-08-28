"""Command line interface for running backtests.

This CLI mirrors the live engine behaviour and reads configuration from
YAML with optional overrides supplied on the command line.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dateutil.relativedelta import relativedelta

from backtest.core.backtest_engine import run_symbol
from backtest.core.config_loader import deep_update, load_config
from backtest.core.logger import setup_logger
from backtest.core.reporting import write_json
from backtest.core.walkforward import WFSpec, build_wf_windows, parse_wf
from tqdm.auto import tqdm


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""

    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, help="Path to YAML config.")
    p.add_argument(
        "--mode",
        choices=["insample", "oos", "walkforward"],
        help="Override backtest.mode.",
    )
    p.add_argument(
        "--oos_last_k_months",
        type=int,
        help="Override YAML OOS months.",
    )
    p.add_argument(
        "--walkforward",
        help='Override YAML walkforward e.g. "train=3,test=1,step=1"',
    )
    p.add_argument("--symbols", help="Filter symbols: comma-separated.")
    p.add_argument(
        "--start",
        help="Start ISO timestamp (UTC). e.g. 2025-01-01T00:00:00",
    )
    p.add_argument(
        "--end",
        help="End ISO timestamp (UTC). e.g. 2025-07-01T00:00:00",
    )
    p.add_argument("--data-root", dest="data_root", help="Path to data root.")
    p.add_argument("--workers", type=int, help="Worker processes for symbol loops.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--progress",
        choices=["off", "fold", "symbol", "bar"],
        default="symbol",
        help="Progress display: off, fold-only, per-symbol, or per-bar.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Load config and show resolved settings without executing.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    # Override via CLI (CLI > YAML > defaults)
    overrides: Dict[str, Dict[str, Any]] = {"backtest": {}}
    if args.mode:
        overrides["backtest"]["mode"] = args.mode
    if args.oos_last_k_months is not None:
        if args.oos_last_k_months <= 0:
            raise SystemExit("--oos_last_k_months must be positive")
        overrides["backtest"]["oos_last_k_months"] = args.oos_last_k_months
    if args.walkforward:
        try:
            wf = parse_wf(args.walkforward)
        except ValueError as e:  # pragma: no cover - validated in unit tests
            raise SystemExit(f"invalid --walkforward: {e}")
        overrides["backtest"]["walkforward"] = {
            "train_months": wf.train_months,
            "test_months": wf.test_months,
            "step_months": wf.step_months,
        }
        overrides["backtest"]["mode"] = "walkforward"
    if args.data_root:
        overrides["paths"] = {"data_root": args.data_root}
    if args.workers is not None:
        if args.workers <= 0:
            raise SystemExit("--workers must be positive")
        overrides["backtest"]["workers"] = args.workers

    cfg = deep_update(cfg, overrides)

    if args.dry_run:
        print(json.dumps(cfg.get("backtest", {}), indent=2))
        return

    mode = cfg.get("backtest", {}).get("mode", "insample")
    data_root = Path(cfg.get("paths", {}).get("data_root", "data"))
    outputs_dir = Path(cfg.get("paths", {}).get("outputs_dir", "outputs"))
    symbols = cfg.get("symbols", ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    outputs_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(str(outputs_dir / "logs/backtest.log"))

    logger.info("=== BACKTEST RUN START ===")
    logger.info(
        f"mode={mode} symbols={symbols} data_root={data_root} start={args.start} end={args.end}"
    )
    if os.environ.get("LIVE_ENGINE_PACKAGE"):
        logger.info(f"LIVE_ENGINE_PACKAGE={os.environ['LIVE_ENGINE_PACKAGE']}")

    summaries: Dict[str, Any] = {}
    if mode == "insample":
        sym_iter = symbols
        if args.progress in ("symbol", "bar"):
            sym_iter = tqdm(
                symbols,
                desc="symbols",
                unit="symbol",
                dynamic_ncols=True,
                mininterval=0.2,
                smoothing=0.1,
            )
        for sym in sym_iter:
            summaries[sym] = run_symbol(
                sym,
                data_root,
                args.start,
                args.end,
                cfg,
                outputs_dir,
                logger,
                progress=(args.progress == "bar"),
            )
    elif mode == "oos":
        k = cfg.get("backtest", {}).get("oos_last_k_months", 1)
        end_iso = args.end or datetime.utcnow().isoformat()
        start_iso = (datetime.fromisoformat(end_iso) - relativedelta(months=k)).isoformat()
        sym_iter = symbols
        if args.progress in ("symbol", "bar"):
            sym_iter = tqdm(
                symbols,
                desc="symbols",
                unit="symbol",
                dynamic_ncols=True,
                mininterval=0.2,
                smoothing=0.1,
            )
        for sym in sym_iter:
            summaries[sym] = run_symbol(
                sym,
                data_root,
                start_iso,
                end_iso,
                cfg,
                outputs_dir,
                logger,
                progress=(args.progress == "bar"),
            )
    elif mode == "walkforward":
        wf_cfg = cfg["backtest"]["walkforward"]
        wf = WFSpec(**wf_cfg)
        if not args.start or not args.end:
            logger.warning(
                "walkforward requires --start and --end for deterministic windows."
            )
        windows = build_wf_windows(
            args.start or "2025-01-01T00:00:00",
            args.end or "2025-08-01T00:00:00",
            wf,
        )
        fold_iter = enumerate(windows)
        if args.progress != "off":
            fold_iter = enumerate(
                tqdm(
                    windows,
                    desc="folds",
                    unit="fold",
                    dynamic_ncols=True,
                    mininterval=0.2,
                    smoothing=0.1,
                )
            )
        for idx, (train_s, train_e, test_s, test_e) in fold_iter:
            logger.info(
                f"WALKFORWARD fold={idx} train=[{train_s}..{train_e}) test=[{test_s}..{test_e})"
            )
            sym_iter = symbols
            if args.progress in ("symbol", "bar"):
                sym_iter = tqdm(
                    symbols,
                    desc=f"fold {idx} symbols",
                    unit="symbol",
                    dynamic_ncols=True,
                    leave=False,
                    mininterval=0.2,
                    smoothing=0.1,
                )
            for sym in sym_iter:
                key = f"{sym}/fold_{idx}"
                summaries[key] = run_symbol(
                    sym,
                    data_root,
                    test_s,
                    test_e,
                    cfg,
                    outputs_dir,
                    logger,
                    progress=(args.progress == "bar"),
                )

    write_json(outputs_dir / "backtest/summary.json", summaries)
    logger.info("=== BACKTEST RUN DONE ===")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()

