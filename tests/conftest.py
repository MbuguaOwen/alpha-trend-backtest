import os
import pytest

LIVE_PKG = os.environ.get("LIVE_ENGINE_PACKAGE")

def pytest_report_header(config):
    return f"LIVE_ENGINE_PACKAGE={LIVE_PKG or 'None'}"
