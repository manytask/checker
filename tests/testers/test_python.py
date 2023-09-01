from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from checker.exceptions import StylecheckFailedError, TestsFailedError
from checker.testers.python import PythonTester


py_tests = pytest.mark.skipif("not config.getoption('python')")


@pytest.fixture(scope='function')
def python_tester() -> PythonTester:
    return PythonTester(cleanup=True, dry_run=False)


def create_single_file_task(
        path: Path,
        file_content: str,
        public_tests: str = '',
        private_tests: str = '',
        tester_config: str = '{}',
        setup_file: str = '',
        *,
        task_name: str = 'task.py',
) -> None:
    files = {task_name: file_content}
    if public_tests:
        files['test_public.py'] = public_tests
    if private_tests:
        files['test_private.py'] = private_tests
    if tester_config:
        files['.tester.json'] = tester_config
    if setup_file:
        files['setup.py'] = setup_file
    create_task(path, files)


def create_task(path: Path, files: dict[str, str]) -> None:
    for filename, content in files.items():
        with open(path / filename, 'w') as f:
            content = inspect.cleandoc(content)
            if not content.endswith('\n\n'):
                content += '\n'
            f.write(content)


@py_tests
class TestPythonTester:
    def test_simple_task(
            self,
            tmp_path: Path,
            python_tester: PythonTester,
            capsys: pytest.CaptureFixture[str],
    ) -> None:
        CODE = """
        def foo() -> str:
            return 'Hello world!'
        """
        PUBLIC_TESTS = """
        from task import foo
        
        
        def test_foo() -> None:
            assert foo() == 'Hello world!'
        """
        PRIVATE_TESTS = """
        def test_nothing() -> None:
            assert True
        """
        create_single_file_task(tmp_path, CODE, PUBLIC_TESTS, PRIVATE_TESTS)

        score = python_tester.test_task(tmp_path, tmp_path, tmp_path, normalize_output=True)
        assert score == 1

        captures = capsys.readouterr()
        assert 'Running codestyle checks...' in captures.err
        assert 'Running mypy checks...' in captures.err
        assert 'Running tests' in captures.err
        assert '2 passed' in captures.err

    def test_mypy_error(
            self,
            tmp_path: Path,
            python_tester: PythonTester,
    ) -> None:
        CODE = """
        def foo() -> int:
            return 'Hello world!'
        """
        PUBLIC_TESTS = """
        def test_nothing() -> None:
            assert True
        """
        create_single_file_task(tmp_path, CODE, PUBLIC_TESTS)

        with pytest.raises(StylecheckFailedError):
            python_tester.test_task(tmp_path, tmp_path, tmp_path, normalize_output=True)

    def test_disabled_mypy_error(
            self,
            tmp_path: Path,
            python_tester: PythonTester,
            capsys: pytest.CaptureFixture[str],
    ) -> None:
        CODE = """
        def foo() -> int:
            return 'Hello world!'
        """
        PUBLIC_TESTS = """
        def test_nothing() -> None:
            assert True
        """
        CONFIG = """
        {"run_mypy": false}
        """
        create_single_file_task(tmp_path, CODE, PUBLIC_TESTS, tester_config=CONFIG)

        python_tester.test_task(tmp_path, tmp_path, tmp_path, normalize_output=True)

        captures = capsys.readouterr()
        assert 'Running mypy checks...' not in captures.err

    def test_flake8_error(
            self,
            tmp_path: Path,
            python_tester: PythonTester,
    ) -> None:
        CODE = """
        def foo() -> str:
            return      'Hello world!'
        """
        PUBLIC_TESTS = """
        def test_nothing() -> None:
            assert True
        """
        CONFIG = """
        {"run_mypy": false}
        """
        create_single_file_task(tmp_path, CODE, PUBLIC_TESTS, tester_config=CONFIG)

        with pytest.raises(StylecheckFailedError):
            python_tester.test_task(tmp_path, tmp_path, tmp_path, normalize_output=True)

    def test_ruff_error(
            self,
            tmp_path: Path,
            python_tester: PythonTester,
    ) -> None:
        CODE = """
        def foo() -> str:
            return 'Hello looolooolooolooolooolooollooolooolooolooolooolooolooolooolooolooolooolooolooolooolooolooolooolooolooolooolooolooolooo world!'
        """
        PUBLIC_TESTS = """
        def test_nothing() -> None:
            assert True
        """
        CONFIG = """
        {"run_mypy": false}
        """
        create_single_file_task(tmp_path, CODE, PUBLIC_TESTS, tester_config=CONFIG)

        with pytest.raises(StylecheckFailedError):
            python_tester.test_task(tmp_path, tmp_path, tmp_path, normalize_output=True)

    def test_pytest_error(
            self,
            tmp_path: Path,
            python_tester: PythonTester,
    ) -> None:
        CODE = """
        def foo() -> str:
            return 'Hello world!'
        """
        PUBLIC_TESTS = """
        def test_nothing() -> None:
            assert False
        """
        CONFIG = """
        {"run_mypy": false}
        """
        create_single_file_task(tmp_path, CODE, PUBLIC_TESTS, tester_config=CONFIG)

        with pytest.raises(TestsFailedError) as ex:
            python_tester.test_task(tmp_path, tmp_path, tmp_path, normalize_output=True)

    def test_pytest_error_no_duble_error(
            self,
            tmp_path: Path,
            python_tester: PythonTester,
            capsys: pytest.CaptureFixture[str],
    ) -> None:
        CODE = """
        def foo() -> str:
            return 'Hello world!'
        """
        PUBLIC_TESTS = """
        def test_nothing() -> None:
            assert False
        """
        CONFIG = """
        {"run_mypy": false}
        """
        with capsys.disabled():
            create_single_file_task(tmp_path, CODE, PUBLIC_TESTS, tester_config=CONFIG)

        with pytest.raises(TestsFailedError) as ex:
            python_tester.test_task(tmp_path, tmp_path, tmp_path, normalize_output=True)
        captured = capsys.readouterr()

        assert captured.err.count('short test summary info ') == 1

    def test_wheel_build(
            self,
            tmp_path: Path,
            python_tester: PythonTester,
            capsys: pytest.CaptureFixture[str],
    ) -> None:
        CODE = """
        def foo() -> str:
            return 'Hello world!'
        """
        PUBLIC_TESTS = """
        def test_nothing() -> None:
            assert True
        """
        SETUP = """
        from setuptools import setup

        setup(name="foo_pkg")
        """
        CONFIG = """
        {"run_mypy": false, "module_test": true, "build_wheel": true}
        """
        create_single_file_task(tmp_path, CODE, PUBLIC_TESTS, tester_config=CONFIG, setup_file=SETUP)

        score = python_tester.test_task(tmp_path, tmp_path, tmp_path, normalize_output=True)
        assert score == 1

        captures = capsys.readouterr()
        assert 'Running mypy checks...' not in captures.err
