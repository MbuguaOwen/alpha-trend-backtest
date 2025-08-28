import pytest

from backtest.core.walkforward import parse_wf


def test_parse_wf_valid() -> None:
    spec = parse_wf("train=3,test=1,step=1")
    assert spec.train_months == 3
    assert spec.test_months == 1
    assert spec.step_months == 1


@pytest.mark.parametrize("bad", ["train=-1,test=1,step=1", "train=3,test=1,step=2", "bad"])
def test_parse_wf_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_wf(bad)

