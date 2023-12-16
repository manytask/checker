import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--skip-integration",
        action="store_true",
        dest="skip_integration",
        default=False,
        help="skip integration tests",
    )
    parser.addoption(
        "--skip-unit",
        action="store_true",
        dest="skip_unit",
        default=False,
        help="skip unit tests",
    )
    parser.addoption(
        "--skip-doctest",
        action="store_true",
        dest="skip_unit",
        default=False,
        help="skip doctest",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: mark test as integration test")

    # Add --doctest-modules by default if --skip-doctest is not set
    if not config.getoption("--skip-doctest"):
        config.addinivalue_line("addopts", "--doctest-modules")


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    skip_integration = pytest.mark.skip(reason="--skip-integration option was provided")
    skip_unit = pytest.mark.skip(reason="--skip-unit option was provided")
    skip_doctest = pytest.mark.skip(reason="--skip-doctest option was provided")

    for item in items:
        if isinstance(item, pytest.DoctestItem):
            item.add_marker(skip_doctest)
        elif "integration" in item.keywords:
            if config.getoption("--skip-integration"):
                item.add_marker(skip_integration)
        else:
            if config.getoption("--skip-unit"):
                item.add_marker(skip_unit)
