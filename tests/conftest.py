import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        '--integration',
        action='store_true',
        dest="integration",
        default=False,
        help="enable integration tests",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: mark test as integration test")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--integration"):
        # --integration given in cli: do not skip integration tests
        return

    skip_integration = pytest.mark.skip(reason="need --integration option to run")

    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
