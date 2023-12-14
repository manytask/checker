from __future__ import annotations

import copy
from typing import Any, Type

import pytest

from checker.configs import PipelineStageConfig
from checker.exceptions import BadConfig, PluginExecutionFailed
from checker.plugins import PluginABC
from checker.plugins.base import PluginOutput
from checker.tester.pipeline import PipelineRunner


class _FailPlugin(PluginABC):
    name = "fail"

    def _run(self, args: PluginABC.Args, *, verbose: bool = False) -> PluginOutput:
        raise PluginExecutionFailed("Failed")


class _ScorePlugin(PluginABC):
    name = "score"

    class Args(PluginABC.Args):
        score: float = 0.5

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        return PluginOutput(output=f"Score: {args.score:.2f}", percentage=args.score)


class _EchoPlugin(PluginABC):
    name = "echo"

    class Args(PluginABC.Args):
        message: str

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        if verbose:
            return PluginOutput(output=args.message)
        else:
            return PluginOutput(output="")


@pytest.fixture
def sample_plugins() -> dict[str, Type[PluginABC]]:
    return {
        "fail": _FailPlugin,
        "score": _ScorePlugin,
        "echo": _EchoPlugin,
    }


@pytest.fixture
def sample_correct_pipeline() -> list[PipelineStageConfig]:
    return [
        PipelineStageConfig(
            name="stage1 - echo",
            run="echo",
            args={"message": "${{ message }}"},
        ),
        PipelineStageConfig(
            name="stage2 - score",
            run="score",
            args={"score": 0.5},
            register_output="score",
        ),
        PipelineStageConfig(
            name="stage3 - ignore fail",
            run="fail",
            fail="never",
        ),
        PipelineStageConfig(
            name="stage4 - skip fail if true",
            run="fail",
            run_if=True,
        ),
        PipelineStageConfig(
            name="stage4 - skip fail if registered output",
            run="fail",
            run_if="${{ outputs.score.percentage > 0.7 }}",
        ),
    ]


class TestSampleFixtures:
    def test_plugins(self, sample_plugins: dict[str, Type[PluginABC]]) -> None:
        plugin = sample_plugins["echo"]()
        plugin.validate({"message": "Hello"})
        result = plugin.run({"message": "Hello"}, verbose=True)
        assert result.percentage is None
        assert result.output == "Hello"

        plugin = sample_plugins["score"]()
        plugin.validate({"score": 0.2})
        result = plugin.run({"score": 0.2})
        assert result.percentage == 0.2
        assert result.output == "Score: 0.20"

        plugin = sample_plugins["fail"]()
        plugin.validate({})
        with pytest.raises(PluginExecutionFailed):
            plugin.run({})


class TestPipelineRunnerValidation:
    def test_correct_pipeline(self, sample_correct_pipeline: list[PipelineStageConfig], sample_plugins: dict[str, Type[PluginABC]]) -> None:
        pipeline_runner = PipelineRunner(
            pipeline=sample_correct_pipeline,
            plugins=sample_plugins,
            verbose=False,
        )
        pipeline_runner.validate({}, validate_placeholders=False)
        pipeline_runner.validate({'message': 'Hello'}, validate_placeholders=True)
        with pytest.raises(BadConfig):
            pipeline_runner.validate({}, validate_placeholders=True)

    def test_unknown_plugin(self, sample_plugins: dict[str, Type[PluginABC]]) -> None:
        with pytest.raises(BadConfig) as exc_info:
            pipeline_runner = PipelineRunner(
                pipeline=[
                    PipelineStageConfig(
                        name="stage1 - echo",
                        run="unknown",
                        args={"message": "Hello"},
                    ),
                ],
                plugins=sample_plugins,
                verbose=False,
            )
        assert "Unknown plugin" in str(exc_info.value)

    # def test_validate_placeholders(self, sample_correct_pipeline: list[PipelineStageConfig]) -> None:
    #     pipeline_runner = PipelineRunner(
    #         pipeline=sample_correct_pipeline,
    #         plugins={},
    #         verbose=False,
    #     )
    #     with pytest.raises(BadConfig) as exc_info:
    #         pipeline_runner.validate({}, validate_placeholders=True)
    #     assert "Unknown plugin" in str(exc_info.value)
    #
    # def test_unknown_placeholder(self, sample_correct_pipeline: list[PipelineStageConfig], sample_plugins: dict[str, Type[PluginABC]]) -> None:
    #     pipeline_runner = PipelineRunner(
    #         pipeline=sample_correct_pipeline,
    #         plugins=sample_plugins,
    #         verbose=False,
    #     )
    #     with pytest.raises(BadConfig) as exc_info:
    #         pipeline_runner.validate({}, validate_placeholders=True)
    #     assert "Unknown placeholder" in str(exc_info.value)
    #
    # def test_invalid_run_if(self, sample_correct_pipeline: list[PipelineStageConfig], sample_plugins: dict[str, Type[PluginABC]]) -> None:
    #     pipeline_runner = PipelineRunner(
    #         pipeline=sample_correct_pipeline,
    #         plugins=sample_plugins,
    #         verbose=False,
    #     )
    #     with pytest.raises(BadConfig) as exc_info:
    #         pipeline_runner.validate({"score": 0.5}, validate_placeholders=True)
    #
