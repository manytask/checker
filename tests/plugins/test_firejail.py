from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from checker.plugins.firejail import SafeRunScriptPlugin
from checker.exceptions import PluginExecutionFailed


PATTERN_ENV = re.compile(r"(?P<name>\S+)=.*")
PATH = "PATH"
PYTHONPATH = "PYTHONPATH"


class TestSafeRunScriptPlugin:
    @pytest.mark.parametrize(
        "parameters, expected_exception",
        [
            ({"origin": "/tmp/123", "script": "echo Hello"}, None),
            ({"origin": "/tmp/123", "script": 123}, ValidationError),
            ({"origin": "/tmp/123", "script": ["echo", "Hello"]}, None),
            ({"origin": "/tmp/123", "script": "echo Hello", "timeout": 10}, None),
        ],
    )
    def test_plugin_args(
        self, parameters: dict[str, Any], expected_exception: Exception | None
    ) -> None:
        if expected_exception:
            with pytest.raises(expected_exception):
                SafeRunScriptPlugin.Args(**parameters)
        else:
            SafeRunScriptPlugin.Args(**parameters)

    @pytest.mark.parametrize(
        "script, output, expected_exception",
        [
            ("echo Hello", "Hello", None),
            ("sleep 0.1", "", None),
            ("true", "", None),
            ("false", "", PluginExecutionFailed),
            ("echo Hello && false", "Hello", PluginExecutionFailed),
        ],
    )
    def test_run_script(
        self, script: str, output: str, expected_exception: Exception | None
    ) -> None:
        plugin = SafeRunScriptPlugin()
        args = SafeRunScriptPlugin.Args(origin="/tmp", script=script)

        if expected_exception:
            with pytest.raises(expected_exception) as exc_info:
                plugin._run(args)
            assert output in exc_info.value.output
        else:
            res = plugin._run(args)
            assert res.output.strip() == output

    @pytest.mark.parametrize(
        "script, timeout, expected_exception",
        [
            ("echo Hello", 10, None),
            ("sleep 0.5", 1, None),
            ("sleep 1", None, None),
            ("sleep 2", 1, PluginExecutionFailed),
        ],
    )
    def test_timeout(
        self, script: str, timeout: float, expected_exception: Exception | None
    ) -> None:
        # TODO: check if timeout float
        plugin = SafeRunScriptPlugin()
        args = SafeRunScriptPlugin.Args(origin="/tmp", script=script, timeout=timeout)

        if expected_exception:
            with pytest.raises(expected_exception):
                plugin._run(args)
        else:
            plugin._run(args)

    @pytest.mark.parametrize(
        "allow_envs",
        [
            ([]),
            ([PATH]),
            ([PATH, PYTHONPATH]),
        ],
    )
    def test_hide_evns(self, allow_envs: list[str]) -> None:
        plugin = SafeRunScriptPlugin()
        args = SafeRunScriptPlugin.Args(
            origin="/tmp", script="printenv", allow_envs=allow_envs
        )

        res_lines = [line.strip() for line in plugin._run(args).output.splitlines()]
        envs: list[str] = []
        for line in res_lines:
            match = PATTERN_ENV.match(line)
            if match and not match.group("name").startswith("-"):
                envs.append(match.group("name"))

        # check if environment has only two items: PATH and PYTHONPATH
        assert len(envs) == len(allow_envs)
        for env in envs:
            assert env in allow_envs

    @pytest.mark.parametrize(
        "query",
        [
            ("curl -i -X GET https://www.example.org"),
            ("curl --user daniel:secret ftp://example.com/download"),
        ],
    )
    def test_allow_network_access(self, query: str) -> None:
        # TODO: have to mock network and check if lock_network = False allows access to the Internet
        plugin = SafeRunScriptPlugin()
        args = SafeRunScriptPlugin.Args(origin="/tmp", script=query, lock_network=True)

        with pytest.raises(PluginExecutionFailed):
            plugin._run(args)

    @pytest.mark.parametrize(
        "origin, allow_paths, access_file, expected_exception",
        [
            ("/tmp", [], Path("/tmp/tmp.txt"), None),
            (
                "/tmp",
                [],
                Path.home().joinpath("tmp", "tmp.txt"),
                None,
            ),  # this is a trick!!! origin /tmp is replaced by ~/tmp
            ("/tmp", [], Path.home().joinpath("tmp.txt"), PluginExecutionFailed),
            ("/tmp", ["~"], Path.home().joinpath("tmp.txt"), None),
            ("~", [], Path.home().joinpath("tmp.txt"), None),
            (
                "/tmp",
                [],
                Path.home().joinpath("not_tmp", "tmp.txt"),
                PluginExecutionFailed,
            ),
            ("/tmp", ["~/not_tmp"], Path.home().joinpath("not_tmp", "tmp.txt"), None),
            ("~/not_tmp", [], Path.home().joinpath("not_tmp", "tmp.txt"), None),
            ("~", [], Path.home().joinpath("tmp.txt"), None),
            ("~/not_tmp", [], Path.home().joinpath("tmp.txt"), PluginExecutionFailed),
            ("~/not_tmp", ["~"], Path.home().joinpath("tmp.txt"), None),
            ("~", [], Path.home().joinpath("tmp", "tmp.txt"), None),
            ("~/not_tmp", ["~"], Path.home().joinpath("tmp", "tmp.txt"), None),
            ("~", [], Path.home().joinpath("not_tmp", "tmp.txt"), None),
            ("~/tmp", [], Path.home().joinpath("tmp", "tmp.txt"), None),
            ("~/not_tmp", ["~/tmp"], Path.home().joinpath("tmp", "tmp.txt"), None),
            ("~/tmp", [], Path.home().joinpath("tmp.txt"), PluginExecutionFailed),
            (
                "~/not_tmp",
                ["~/tmp"],
                Path.home().joinpath("tmp.txt"),
                PluginExecutionFailed,
            ),
            (
                "~/tmp",
                [],
                Path.home().joinpath("not_tmp", "tmp.txt"),
                PluginExecutionFailed,
            ),
            (
                "/tmp",
                ["~/tmp"],
                Path.home().joinpath("not_tmp", "tmp.txt"),
                PluginExecutionFailed,
            ),
        ],
    )
    def test_file_system_access(
        self,
        origin: str,
        allow_paths: list[str],
        access_file: Path,
        expected_exception: Exception | None,
    ) -> None:
        access_file_path = access_file
        access_file_path.parent.mkdir(parents=True, exist_ok=True)
        access_file_path.touch()

        Path(origin).mkdir(parents=True, exist_ok=True)

        plugin = SafeRunScriptPlugin()
        args = SafeRunScriptPlugin.Args(
            origin=str(origin),
            allow_paths=allow_paths,
            script=f"cat {str(access_file)}",
        )

        if expected_exception:
            with pytest.raises(expected_exception):
                plugin._run(args)
        else:
            plugin._run(args)

        access_file_path.unlink()
