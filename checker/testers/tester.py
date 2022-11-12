from __future__ import annotations

import json
import tempfile
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..exceptions import RunFailedError, TaskTesterTestConfigException, TesterNotImplemented
from ..executors.sandbox import Sandbox
from ..utils.print import print_info


class Tester:
    """Entrypoint to testing system
    Tester holds the course object and manage testing of single tasks,
    as well as manage Tasks-Folders mapping
    (Task names for tests should be provided)
    """

    SOURCE_FILES_EXTENSIONS: list[str] = []
    __test__ = False  # to disable pytest detecting it as Test class

    @dataclass
    class TaskTestConfig:
        """Task Tests Config
        Configure how task will copy files, check, execute and so on
        """
        pass

        @classmethod
        def from_json(
                cls,
                test_config: Path,
        ) -> 'Tester.TaskTestConfig':
            """
            Create TaskTestConfig from json config
            @param test_config: Path to the config
            @return: TaskTestConfig object
            """
            try:
                task_config_path = test_config
                if task_config_path.exists():
                    with open(task_config_path) as f:
                        raw_config = json.load(f)
                    if not isinstance(raw_config, dict):
                        raise TaskTesterTestConfigException(f'Got <{type(raw_config).__name__}> instead of <dict>')
                else:
                    raw_config = {}
            except (json.JSONDecodeError, TypeError) as e:
                raise TaskTesterTestConfigException(f'Got invalid Test Config <{test_config}>') from e

            # Go throughout config fields and pop it from json if any
            config_kwargs: dict[str, Any] = {}
            for config_field in cls.__annotations__:
                if (field_value := raw_config.pop(config_field, None)) is not None:
                    config_kwargs[config_field] = field_value

            if raw_config:
                bad_keys = ','.join(raw_config.keys())
                raise TaskTesterTestConfigException(f'Test Config {test_config} has unknown key(s) <{bad_keys}>')

            return cls(**config_kwargs)

    def __init__(
            self,
            cleanup: bool = True,
            dry_run: bool = False,
    ):
        self.cleanup = cleanup
        self.dry_run = dry_run
        self._executor = Sandbox(dry_run=dry_run)

    @classmethod
    def create(
            cls,
            system: str,
            cleanup: bool = True,
            dry_run: bool = False,
    ) -> 'Tester':
        """
        Main creation entrypoint to Tester
        Create one of existed Testers (python, cpp, etc.)
        @param system: Type of the testing system
        @param cleanup: Perform cleanup after testing
        @param dry_run: Setup dry run mode (really executes nothing)
        @return: Configured Tester object (python, cpp, etc.)
        """
        if system == 'python':
            from . import python
            return python.PythonTester(cleanup=cleanup, dry_run=dry_run)
        elif system == 'make':
            from . import make
            return make.MakeTester(cleanup=cleanup, dry_run=dry_run)
        elif system == 'cpp':
            from . import cpp
            return cpp.CppTester(cleanup=cleanup, dry_run=dry_run)
        else:
            raise TesterNotImplemented(f'Tester for <{system}> are not supported right now')

    @abstractmethod
    def _gen_build(
            self,
            test_config: TaskTestConfig,
            build_dir: Path,
            source_dir: Path,
            public_tests_dir: Path,
            private_tests_dir: Path,
            sandbox: bool = True,
            verbose: bool = False,
            normalize_output: bool = False,
    ) -> None:  # pragma: nocover
        """
        Copy all files for testing and build the program (if necessary)
        @param test_config: Test config to pass into each stage
        @param build_dir: Directory to copy files into and build there
        @param source_dir: Solution source code directory
        @param public_tests_dir: Directory to copy public tests from
        @param private_tests_dir: Directory to copy private tests from
        @param sandbox: Wrap all student's code to sandbox; @see Executor.sandbox
        @param verbose: Verbose output (can exhibit private tests information)
        @param normalize_output: Normalize all stages output to stderr
        @return: None
        """
        pass

    @abstractmethod
    def _clean_build(
            self,
            test_config: TaskTestConfig,
            build_dir: Path,
            verbose: bool = False,
    ) -> None:  # pragma: nocover
        """
        Clean build directory after testing
        @param test_config: Test config to pass into each stage
        @param build_dir: Build directory to clean up
        @param verbose: Verbose output (can exhibit private tests information)
        @return: None
        """
        pass

    @abstractmethod
    def _run_tests(
            self,
            test_config: TaskTestConfig,
            build_dir: Path,
            sandbox: bool = False,
            verbose: bool = False,
            normalize_output: bool = False,
    ) -> float:  # pragma: nocover
        """
        Run tests for already built task and return solution score
        @param test_config: Test config to pass into each stage
        @param build_dir: Directory with task ready for testing
        @param sandbox: Wrap all student's code to sandbox; @see Executor.sandbox
        @param verbose: Verbose output (can exhibit private tests information)
        @param normalize_output: Normalize all stages output to stderr
        @return: Percentage of the final score
        """
        pass

    def test_task(
            self,
            source_dir: Path,
            public_tests_dir: Path,
            private_tests_dir: Path,
            verbose: bool = False,
            normalize_output: bool = False,
    ) -> float:
        """ Inner function to test the task (Folders already specified)
        Perform the following actions:
        * _gen_build: copy source and test files, check forbidden regxp, build and install if necessary
        * _run_tests: run testing and linting
        * _clean_build: cleanup if necessary
        @param source_dir: Solution dir (student's solution or authors' solution)
        @param public_tests_dir: Directory to copy public tests from
        @param private_tests_dir: Directory to copy private tests from
        @param verbose: Verbose output (can exhibit private tests information)
        @param normalize_output: Normalize all stages output to stderr
        @raise RunFailedError: on any build/test error
        @return: Percentage of the final score
        """
        # Read test config
        test_config = self.TaskTestConfig.from_json(private_tests_dir / '.tester.json')

        # Create build dir as tmp dir
        build_dir = Path(tempfile.mkdtemp())
        build_dir.chmod(0o777)  # Set mode for build directory (for code generation and so on)

        try:
            self._gen_build(
                test_config,
                build_dir,
                source_dir,
                public_tests_dir,
                private_tests_dir,
                sandbox=True,
                verbose=verbose,
                normalize_output=normalize_output,
            )

            # Do not disable sandbox (otherwise it will not clear environ,
            # so environ-related issues may be missed, such as empty locale)
            score_percentage = self._run_tests(
                test_config,
                build_dir,
                sandbox=True,
                verbose=verbose,
                normalize_output=normalize_output
            )
        except RunFailedError as e:
            print_info('\nOoops... Something went wrong: ' + e.msg + (e.output or ''), color='red')
            raise e
        finally:
            if self.cleanup:
                self._clean_build(
                    test_config,
                    build_dir,
                    verbose=verbose
                )
            else:
                print_info(f'Keeping build directory: {build_dir}')

        return score_percentage
