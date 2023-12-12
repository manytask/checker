from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
import subprocess

import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from checker.plugins.scripts import RunScriptPlugin
from checker.exceptions import ExecutionFailedError


class TestRunScriptPlugin:

    @pytest.mark.parametrize("parameters, expected_exception", [
        ({'origin': '/tmp/123', 'script': 'echo Hello'}, None),
        ({'origin': '/tmp/123', 'script': 123}, ValidationError),
        ({'origin': '/tmp/123', 'script': ['echo', 'Hello']}, None),
        ({'origin': '/tmp/123', 'script': 'echo Hello', 'timeout': 10}, None),
        # ({'origin': '/tmp/123', 'script': 'echo Hello', 'timeout': '10'}, ValidationError),
        ({'origin': '/tmp/123', 'script': 'echo Hello', 'isolate': True}, None),
        ({'origin': '/tmp/123', 'script': 'echo Hello', 'env_whitelist': ['PATH']}, None),
    ])
    def test_plugin_args(self, parameters: dict[str, Any], expected_exception: Exception | None) -> None:
        if expected_exception:
            with pytest.raises(expected_exception):
                RunScriptPlugin.Args(**parameters)
        else:
            RunScriptPlugin.Args(**parameters)

    @pytest.mark.parametrize("script, output, expected_exception", [
        ("echo Hello", "Hello", None),
        ("sleep 0.1", "", None),
        ("true", "", None),
        ("false", "", ExecutionFailedError),
        ("echo Hello && false", "Hello", ExecutionFailedError),
    ])
    def test_simple_cases(self, script: str, output: str, expected_exception: Exception | None) -> None:
        plugin = RunScriptPlugin()
        args = RunScriptPlugin.Args(origin="/tmp", script=script)

        if expected_exception:
            with pytest.raises(expected_exception) as exc_info:
                plugin._run(args)
            assert output in exc_info.value.output
        else:
            res = plugin._run(args)
            assert res.strip() == output

    @pytest.mark.parametrize("script, timeout, expected_exception", [
        ("echo Hello", 10, None),
        ("sleep 0.5", 1, None),
        ("sleep 1", None, None),
        ("sleep 2", 1, ExecutionFailedError),
    ])
    def test_timeout(self, script: str, timeout: float, expected_exception: Exception | None) -> None:
        # TODO: check if timeout float
        plugin = RunScriptPlugin()
        args = RunScriptPlugin.Args(origin="/tmp", script=script, timeout=timeout)

        if expected_exception:
            with pytest.raises(expected_exception):
                plugin._run(args)
        else:
            plugin._run(args)

    @pytest.mark.parametrize("script, env_whitelist, mocked_env", [
        ("env", ["CUSTOM_VAR"], {"FILTERED_ONE": "1", "CUSTOM_VAR": "test_value"}),
        # TODO: expand this test
    ])
    def test_run_with_environment_variable(self, script: str, env_whitelist: list[str], mocked_env: dict[str, str]) -> None:
        plugin = RunScriptPlugin()
        args = RunScriptPlugin.Args(origin="/tmp", script=script, env_whitelist=env_whitelist)
        
        with patch.dict('os.environ', mocked_env, clear=True):
            output = plugin._run(args)
        assert "CUSTOM_VAR" in output
        assert mocked_env["CUSTOM_VAR"] in output
        assert "FILTERED_ONE" not in output
    