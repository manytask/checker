import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption('--python', action='store_true', dest="python", default=False, help="enable python tests")
    parser.addoption('--cpp', action='store_true', dest="cpp", default=False, help="enable cpp tests")
