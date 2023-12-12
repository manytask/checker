from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from checker.plugins.regex import CheckRegexpsPlugin
from checker.exceptions import ExecutionFailedError


class TestCheckRegexpsPlugin:

    T_CREATE_TEST_FILES = Callable[[dict[str, str]], Path]

    @pytest.fixture
    def create_test_files(self, tmpdir: Path) -> T_CREATE_TEST_FILES:
        def _create_test_files(files_content: dict[str, str]) -> Path:
            for filename, content in files_content.items():
                file = tmpdir / filename
                with open(file, "w") as f:
                    f.write(content)
            return tmpdir
        return _create_test_files

    # TODO: add tests with wrong patterns and regexps
    @pytest.mark.parametrize("parameters, expected_exception", [
        ({'origin': '/tmp/123', 'patterns': ['*', '*.py'], 'regexps': ['error']}, None),
        ({'patterns': ['*', '*.py'], 'regexps': ['error']}, ValidationError),
        ({'origin': '/tmp/123', 'patterns': ['*', '*.py']}, ValidationError),
        ({'origin': '/tmp/123', 'patterns': None, 'regexps': None}, ValidationError),
    ])
    def test_plugin_args(self, parameters: dict[str, Any], expected_exception: Exception | None) -> None:
        if expected_exception:
            with pytest.raises(expected_exception):
                CheckRegexpsPlugin.Args(**parameters)
        else:
            CheckRegexpsPlugin.Args(**parameters)

    @pytest.mark.parametrize("patterns, expected_exception", [
        (["*.txt"], ExecutionFailedError),
        (["test2.txt", "*cpp"], None),
        (["*"], ExecutionFailedError),
        (["*.md"], ExecutionFailedError),
        (["test?.txt"], ExecutionFailedError),
        (["test2.txt", "test1.txt"], ExecutionFailedError),
    ])
    def test_pattern_matching(self, create_test_files: T_CREATE_TEST_FILES, patterns: list[str], expected_exception: Exception | None) -> None:
        files_content = {
            "test1.txt": "This is a test file with forbidden content",
            "test2.txt": "This file is safe",
            "test3.md": "Markdown file with forbidden content",
            "test4.py": "Python file with forbidden content",
            "test5.cpp": "Cpp file with safe content",
        }
        origin = create_test_files(files_content)
        regexps = ["forbidden"]

        plugin = CheckRegexpsPlugin()
        args = CheckRegexpsPlugin.Args(origin=str(origin), patterns=patterns, regexps=regexps)

        if expected_exception:
            with pytest.raises(expected_exception):
                plugin._run(args)
        else:
            assert plugin._run(args) == "No forbidden regexps found"

    @pytest.mark.parametrize("regexps, expected_exception", [
        (["not_found"], None),
        (["forbidden"], ExecutionFailedError),
        (["fo.*en"], ExecutionFailedError),
        (["not_found", "fo.?bi.?den"], ExecutionFailedError),
        (["fo.?bi.?den", "not_found"], ExecutionFailedError),
    ])
    def test_check_regexps(self, create_test_files: T_CREATE_TEST_FILES, regexps: list[str], expected_exception: Exception | None) -> None:
        files_content = {
            "test1.txt": "This is a test file with forbidden content",
            "test2.txt": "This file is safe",
            "test3.md": "Markdown file with forbidden content",
            "test4.py": "Python file with forbidden content",
            "test5.cpp": "Cpp file with safe content",
        }
        origin = create_test_files(files_content)
        patterns = ["*"]

        plugin = CheckRegexpsPlugin()
        args = CheckRegexpsPlugin.Args(origin=str(origin), patterns=patterns, regexps=regexps)

        if expected_exception:
            with pytest.raises(expected_exception) as e:
                plugin._run(args)
            assert "matches regexp" in str(e.value)
        else:
            assert plugin._run(args) == "No forbidden regexps found"
            assert plugin._run(args, verbose=True) == "No forbidden regexps found"
            assert plugin._run(args, verbose=False) == "No forbidden regexps found"

    def test_non_existent_origin(self) -> None:
        plugin = CheckRegexpsPlugin()
        args = CheckRegexpsPlugin.Args(origin="/tmp/non_existent", patterns=["*.txt"], regexps=["forbidden"])

        with pytest.raises(ExecutionFailedError) as e:
            plugin._run(args)
        assert "does not exist" in str(e.value)
