import logging
from pathlib import Path

def setup_logger(logfile: str):
    Path(logfile).parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("backtest")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    fh = logging.FileHandler(logfile)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger
