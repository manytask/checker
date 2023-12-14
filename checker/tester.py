from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .configs import CheckerTestingConfig
from .configs.checker import (
    CheckerConfig,
    CheckerParametersConfig,
    CheckerStructureConfig,
)
from .course import Course, FileSystemTask
from .exceptions import PluginExecutionFailed, TestingError
from .plugins import load_plugins
from .utils import print_header_info, print_info, print_separator
from .pipeline import PipelineResult, PipelineRunner, PipelineStageResult


@dataclass
class GlobalPipelineVariables:
    """Base variables passed in pipeline stages."""

    ref_dir: str
    repo_dir: str
    temp_dir: str
    username: str
    task_names: list[str]
    task_sub_paths: list[str]


@dataclass
class TaskPipelineVariables:
    """Variables passed in pipeline stages for each task."""

    task_name: str
    task_sub_path: str


class Tester:
    """
    Class to encapsulate all testing logic.
    1. Create temporary directory
    2. Execute global pipeline
    3. Execute task pipeline for each task
    4. Collect results and push to them
    5. Remove temporary directory
    """

    __test__ = False  # do not collect this class for pytest

    def __init__(
        self,
        course: Course,
        checker_config: CheckerConfig,
        *,
        cleanup: bool = True,
        verbose: bool = False,
        dry_run: bool = False,
    ):
        """
        Init tester in specific public and private dirs.

        :param course: Course object for iteration with physical course
        :param checker_config: Full checker config with testing,structure and params folders
        :param cleanup: Cleanup temporary directory after testing
        :param verbose: Whatever to print private outputs and debug info
        :param dry_run: Do not execute anything, just print what would be executed
        :raises exception.ValidationError: if config is invalid or repo structure is wrong
        """
        self.course = course

        self.testing_config = checker_config.testing
        self.structure_config = checker_config.structure
        self.default_params = checker_config.default_parameters

        self.plugins = load_plugins(self.testing_config.search_plugins, verbose=verbose)
        self.global_pipeline = PipelineRunner(
            self.testing_config.global_pipeline, self.plugins, verbose=verbose
        )
        self.task_pipeline = PipelineRunner(
            self.testing_config.tasks_pipeline, self.plugins, verbose=verbose
        )
        self.report_pipeline = PipelineRunner(
            self.testing_config.report_pipeline, self.plugins, verbose=verbose
        )

        self.repository_dir = self.course.repository_root
        self.reference_dir = self.course.reference_root
        self._temporary_dir_manager = tempfile.TemporaryDirectory()
        self.temporary_dir = Path(self._temporary_dir_manager.name)

        self.cleanup = cleanup
        self.verbose = verbose
        self.dry_run = dry_run

    def _get_global_pipeline_parameters(
        self, tasks: list[FileSystemTask]
    ) -> GlobalPipelineVariables:
        return GlobalPipelineVariables(
            ref_dir=self.reference_dir.absolute().as_posix(),
            repo_dir=self.repository_dir.absolute().as_posix(),
            temp_dir=self.temporary_dir.absolute().as_posix(),
            username=self.course.username,
            task_names=[task.name for task in tasks],
            task_sub_paths=[task.relative_path for task in tasks],
        )

    def _get_task_pipeline_parameters(
        self, task: FileSystemTask
    ) -> TaskPipelineVariables:
        return TaskPipelineVariables(
            task_name=task.name,
            task_sub_path=task.relative_path,
        )

    def _get_context(
        self,
        global_variables: GlobalPipelineVariables,
        task_variables: TaskPipelineVariables | None,
        outputs: dict[str, PipelineStageResult],
        default_parameters: CheckerParametersConfig,
        task_parameters: CheckerParametersConfig | None,
    ) -> dict[str, Any]:
        return {
            "global": global_variables,
            "task": task_variables,
            "outputs": outputs,
            "parameters": default_parameters.__dict__ | (task_parameters.__dict__ if task_parameters else {}),
            "env": os.environ.__dict__,
        }

    def validate(self) -> None:
        # get all tasks
        tasks = self.course.get_tasks(enabled=True)

        # create outputs to pass to pipeline
        outputs: dict[str, PipelineStageResult] = {}

        # validate global pipeline (only default params and variables available)
        print("- global pipeline...")
        global_variables = self._get_global_pipeline_parameters(tasks)
        context = self._get_context(
            global_variables, None, outputs, self.default_params, None
        )
        self.global_pipeline.validate(context, validate_placeholders=True)
        print("  ok")

        for task in tasks:
            # validate task with global + task-specific params
            print(f"- task {task.name} pipeline...")

            # create task context
            task_variables = self._get_task_pipeline_parameters(task)
            context = self._get_context(
                global_variables,
                task_variables,
                outputs,
                self.default_params,
                task.config.parameters if task.config else None,
            )

            # check task parameter are
            # TODO: read pipeline from task config if any
            self.task_pipeline.validate(context, validate_placeholders=True)
            self.report_pipeline.validate(context, validate_placeholders=True)

            print("  ok")

    def run(
        self,
        tasks: list[FileSystemTask] | None = None,
        report: bool = True,
    ) -> None:
        # copy files for testing
        self.course.copy_files_for_testing(self.temporary_dir)

        # get all tasks
        tasks = tasks or self.course.get_tasks(enabled=True)

        # create outputs to pass to pipeline
        outputs: dict[str, PipelineStageResult] = {}

        # run global pipeline
        print_header_info("Run global pipeline:", color="pink")
        global_variables = self._get_global_pipeline_parameters(tasks)
        context = self._get_context(
            global_variables, None, outputs, self.default_params, None
        )
        global_pipeline_result: PipelineResult = self.global_pipeline.run(
            context, dry_run=self.dry_run
        )
        print_separator("-")
        print_info(str(global_pipeline_result), color="pink")

        if not global_pipeline_result:
            raise TestingError("Global pipeline failed")

        failed_tasks = []
        for task in tasks:
            # run task pipeline
            print_header_info(f"Run <{task.name}> task pipeline:", color="pink")

            # create task context
            task_variables = self._get_task_pipeline_parameters(task)
            context = self._get_context(
                global_variables,
                task_variables,
                outputs,
                self.default_params,
                task.config.parameters if task.config else None,
            )

            # TODO: read pipeline from task config if any
            task_pipeline_result: PipelineResult = self.task_pipeline.run(
                context, dry_run=self.dry_run
            )
            print_separator("-")

            print_info(str(task_pipeline_result), color="pink")
            print_separator("-")

            # Report score if task pipeline succeeded
            if task_pipeline_result:
                print_info(f"Reporting <{task.name}> task tests:", color="pink")
                if report:
                    task_report_result: PipelineResult = self.report_pipeline.run(
                        context, dry_run=self.dry_run
                    )
                    if task_report_result:
                        print_info("->Reporting succeeded")
                    else:
                        print_info("->Reporting failed")
                else:
                    print_info("->Reporting disabled")
                print_separator("-")
            else:
                failed_tasks.append(task.name)

        if failed_tasks:
            raise TestingError(f"Task pipelines failed: {failed_tasks}")

    def __del__(self) -> None:
        # if self.cleanup:
        if self.__dict__.get("cleanup") and self._temporary_dir_manager:
            self._temporary_dir_manager.cleanup()
