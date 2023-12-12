from __future__ import annotations

import tempfile
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..configs import CheckerTestingConfig
from ..configs.checker import CheckerStructureConfig, CheckerConfig
from ..course import Course, FileSystemTask
from ..exceptions import ExecutionFailedError, ExecutionTimeoutError, RunFailedError, TestingError
from .pipeline import PipelineRunner, GlobalPipelineVariables, TaskPipelineVariables, PipelineResult
from ..plugins import load_plugins
from ..utils import print_info, print_header_info, print_separator


class Tester:
    """
    Class to encapsulate all testing logic.
    1. Create temporary directory
    2. Execute global pipeline
    3. Execute task pipeline for each task
    4. Collect results and return them
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
        self.default_params = checker_config.default_params

        self.plugins = load_plugins(self.testing_config.search_plugins, verbose=verbose)
        self.global_pipeline = PipelineRunner(self.testing_config.global_pipeline, self.plugins, verbose=verbose)
        self.task_pipeline = PipelineRunner(self.testing_config.tasks_pipeline, self.plugins, verbose=verbose)
        self.report_pipeline = PipelineRunner(self.testing_config.report_pipeline, self.plugins, verbose=verbose)

        self.repository_dir = self.course.repository_root
        self.reference_dir = self.course.reference_root
        self._temporary_dir_manager = tempfile.TemporaryDirectory()
        self.temporary_dir = Path(self._temporary_dir_manager.name)

        self.cleanup = cleanup
        self.verbose = verbose
        self.dry_run = dry_run

    def _get_global_pipeline_parameters(self, tasks: list[FileSystemTask]) -> dict[str, Any]:
        global_variables = GlobalPipelineVariables(
            REF_DIR=self.reference_dir.absolute().as_posix(),
            REPO_DIR=self.repository_dir.absolute().as_posix(),
            TEMP_DIR=self.temporary_dir.absolute().as_posix(),
            USERNAME=self.course.username,
            TASK_NAMES=[task.name for task in tasks],
            TASK_SUB_PATHS=[task.relative_path for task in tasks],
        )
        global_parameters = self.default_params.__dict__ | global_variables.__dict__
        return global_parameters

    def _get_task_pipeline_parameters(self, global_parameters: dict[str, Any], task: FileSystemTask) -> dict[str, Any]:
        task_variables = TaskPipelineVariables(
            TASK_NAME=task.name,
            TASK_SUB_PATH=task.relative_path,
        )
        task_specific_params = task.config.params if task.config and task.config.params else {}
        task_parameters = (
            global_parameters |
            task_specific_params |
            task_variables.__dict__
        )
        return task_parameters

    def validate(self) -> None:
        # get all tasks
        tasks = self.course.get_tasks(enabled=True)

        # create context to pass to pipeline
        register_global_context: dict[str, float] = {}

        # validate global pipeline (only default params and variables available)
        print("- global pipeline...")
        global_parameters = self._get_global_pipeline_parameters(tasks)
        self.global_pipeline.validate(global_parameters, register_global_context, validate_placeholders=True)
        print("  ok")

        print_info('register_global_context after global_pipeline.validate', register_global_context, color='pink')

        for task in tasks:
            # create task context
            register_task_context = register_global_context.copy()

            # validate task with global + task-specific params
            print(f"- task {task.name} pipeline...")
            # check task parameter are
            task_parameters = self._get_task_pipeline_parameters(global_parameters, task)
            # TODO: read from config task specific pipeline
            self.task_pipeline.validate(task_parameters, register_task_context, validate_placeholders=True)
            self.report_pipeline.validate(task_parameters, register_task_context, validate_placeholders=True)

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

        # create context to pass to pipeline
        register_global_context: dict[str, float] = {}

        # run global pipeline
        print_header_info("Run global pipeline:", color='pink')
        global_parameters = self._get_global_pipeline_parameters(tasks)
        global_pipeline_result: PipelineResult = self.global_pipeline.run(global_parameters, extra_context=register_global_context, dry_run=self.dry_run)
        print_separator('-')
        print_info(str(global_pipeline_result), color='pink')

        if not global_pipeline_result:
            raise TestingError("Global pipeline failed")

        failed_tasks = []
        for task in tasks:
            # create task context
            register_task_context = register_global_context.copy()

            # run task pipeline
            print_header_info(f"Run <{task.name}> task pipeline:", color='pink')
            task_parameters = self._get_task_pipeline_parameters(global_parameters, task)

            # TODO: read from config task specific pipeline
            task_pipeline_result: PipelineResult = self.task_pipeline.run(task_parameters, extra_context=register_task_context, dry_run=self.dry_run)
            print_separator('-')

            print_info(str(task_pipeline_result), color='pink')
            print_separator('-')

            # Report score if task pipeline succeeded
            if task_pipeline_result:
                print_info(f"Reporting <{task.name}> task tests:", color='pink')
                if report:
                    task_report_result: PipelineResult = self.report_pipeline.run(task_parameters, extra_context=register_task_context, dry_run=self.dry_run)
                    if task_report_result:
                        print_info("->Reporting succeeded")
                    else:
                        print_info("->Reporting failed")
                else:
                    print_info("->Reporting disabled")
                print_separator('-')
            else:
                failed_tasks.append(task.name)

        if failed_tasks:
            raise TestingError(f"Task pipelines failed: {failed_tasks}")

    def __del__(self) -> None:
        # if self.cleanup:
        if self.__dict__.get("cleanup") and self._temporary_dir_manager:
            self._temporary_dir_manager.cleanup()
