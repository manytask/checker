import pytest


def pytest_addoption(parser: pytest.Parser):
    parser.addoption('--cpp', action='store_true', dest="cpp", default=False, help="enable cpp tests")
