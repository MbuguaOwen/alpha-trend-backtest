import logging
from pathlib import Path
from tqdm.auto import tqdm


class TqdmHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            # Use tqdm.write to avoid breaking progress bars
            tqdm.write(msg)
        except Exception:
            # Fallback to standard stream handler behavior
            super().emit(record)


def setup_logger(logfile: str):
    Path(logfile).parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("backtest")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    fh = logging.FileHandler(logfile)
    fh.setFormatter(fmt)
    sh = TqdmHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger
