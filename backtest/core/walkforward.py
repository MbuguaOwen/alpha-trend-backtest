from dataclasses import dataclass
from datetime import datetime
from dateutil.relativedelta import relativedelta

@dataclass
class WFSpec:
    """Specification for walk-forward windows (in months)."""

    train_months: int
    test_months: int
    step_months: int


def parse_wf(s: str) -> WFSpec:
    """Parse a walk-forward spec string.

    The expected format is ``"train=3,test=1,step=1"``. Values must be
    positive integers and ``step`` must be less than or equal to ``test``.
    ``ValueError`` is raised on malformed input.
    """

    try:
        parts = dict(p.split("=", 1) for p in s.split(","))
        train = int(parts["train"])
        test = int(parts["test"])
        step = int(parts["step"])
    except Exception as exc:
        raise ValueError("walkforward must be like 'train=3,test=1,step=1'") from exc

    for name, val in ("train", train), ("test", test), ("step", step):
        if val <= 0:
            raise ValueError(f"{name} must be positive")
    if step > test:
        raise ValueError("step must be <= test")

    return WFSpec(train_months=train, test_months=test, step_months=step)

def month_range(start_iso: str, end_iso: str):
    start = datetime.fromisoformat(start_iso.replace("Z",""))
    end = datetime.fromisoformat(end_iso.replace("Z",""))
    cur = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while cur < end:
        nxt = cur + relativedelta(months=1)
        yield cur, nxt
        cur = nxt

def build_wf_windows(start_iso: str, end_iso: str, spec: WFSpec):
    months = list(month_range(start_iso, end_iso))
    if not months:
        return []
    windows = []
    i = 0
    while True:
        train_start = months[i][0]
        train_end = train_start + relativedelta(months=spec.train_months)
        test_end = train_end + relativedelta(months=spec.test_months)
        if test_end > months[-1][1]:
            break
        windows.append((train_start.isoformat(), train_end.isoformat(), train_end.isoformat(), test_end.isoformat()))
        i += spec.step_months
        if i >= len(months):
            break
    return windows
