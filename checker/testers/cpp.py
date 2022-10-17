from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..exceptions import (
    BuildFailedError,
    ExecutionFailedError,
    StylecheckFailedError,
    TestsFailedError,
    TimeoutExpiredError,
)
from ..utils.files import check_files_contains_regexp, copy_files
from ..utils.print import print_info
from .tester import Tester


class CppTester(Tester):

    @dataclass
    class TaskTestConfig(Tester.TaskTestConfig):
        allow_change: list[str] = field(default_factory=list)
        forbidden_regexp: list[str] = field(default_factory=list)
        copy_to_build: list[str] = field(default_factory=list)

        linter: bool = True
        build_type: str = 'Asan'
        is_crash_me: bool = False

        tests: list[str] = field(default_factory=list)
        input_file: dict[str, str] = field(default_factory=dict)
        args: dict[str, list[str]] = field(default_factory=dict)
        timeout: float = 60.
        capture_output: bool = True

        def __post_init__(
                self,
        ) -> None:
            assert self.tests
            assert self.allow_change

    def _gen_build(  # type: ignore[override]
            self,
            test_config: TaskTestConfig,
            build_dir: Path,
            source_dir: Path,
            public_tests_dir: Path,
            private_tests_dir: Path,
            sandbox: bool = True,
            verbose: bool = False,
            normalize_output: bool = False,
    ) -> None:
        check_files_contains_regexp(
            source_dir,
            regexps=test_config.forbidden_regexp,
            patterns=test_config.allow_change,
            raise_on_found=True,
        )
        reference_root = public_tests_dir.parent
        task_name = source_dir.name
        task_dir = reference_root / task_name
        self._executor(
            copy_files,
            source=source_dir,
            target=task_dir,
            patterns=test_config.allow_change,
            verbose=verbose,
        )
        self._executor(
            copy_files,
            source=task_dir,
            target=build_dir,
            patterns=test_config.copy_to_build,
            verbose=verbose,
        )

        try:
            print_info('Running cmake...', color='orange')
            self._executor(
                ['cmake', '-G', 'Ninja', str(reference_root),
                 '-DGRADER=YES', '-DENABLE_PRIVATE_TESTS=YES',
                 f'-DCMAKE_BUILD_TYPE={test_config.build_type}'],
                cwd=build_dir,
                verbose=verbose,
            )
        except ExecutionFailedError:
            print_info('ERROR', color='red')
            raise BuildFailedError('cmake execution failed')

        for test_binary in test_config.tests:
            try:
                print_info(f'Building {test_binary}...', color='orange')
                self._executor(
                    ['ninja', '-v', test_binary],
                    cwd=build_dir,
                    verbose=verbose,
                )
            except ExecutionFailedError:
                print_info('ERROR', color='red')
                raise BuildFailedError(f'Can\'t build {test_binary}')

        if not test_config.linter:
            return

        try:
            print_info('Running clang format...', color='orange')
            format_path = reference_root / 'run-clang-format.py'
            self._executor(
                [str(format_path), '-r', str(task_dir)],
                cwd=build_dir,
                verbose=verbose,
            )
            print_info('[No issues]')
            print_info('OK', color='green')
        except ExecutionFailedError:
            print_info('ERROR', color='red')
            raise StylecheckFailedError('Style error (clang format)')

        try:
            print_info('Running clang tidy...', color='orange')
            files = [str(file) for file in task_dir.rglob('*.cpp')]
            self._executor(
                ['clang-tidy', '-p', '.', *files],
                cwd=build_dir,
                verbose=verbose,
            )
            print_info('[No issues]')
            print_info('OK', color='green')
        except ExecutionFailedError:
            print_info('ERROR', color='red')
            raise StylecheckFailedError('Style error (clang tidy)')

    def _clean_build(  # type: ignore[override]
            self,
            test_config: TaskTestConfig,
            build_dir: Path,
            verbose: bool = False,
    ) -> None:
        self._executor(
            ['rm', '-rf', str(build_dir)],
            check=False,
            verbose=verbose,
        )

    def _run_tests(  # type: ignore[override]
            self,
            test_config: TaskTestConfig,
            build_dir: Path,
            sandbox: bool = False,
            verbose: bool = False,
            normalize_output: bool = False,
    ) -> float:
        for test_binary in test_config.tests:
            stdin = None
            try:
                print_info(f'Running {test_binary}...', color='orange')
                args = test_config.args.get(test_binary, [])
                if test_binary in test_config.input_file:
                    stdin = open(build_dir / test_config.input_file[test_binary], 'r')
                self._executor(
                    [str(build_dir / test_binary), *args],
                    sandbox=True,
                    cwd=build_dir,
                    verbose=verbose,
                    capture_output=test_config.capture_output,
                    timeout=test_config.timeout,
                    stdin=stdin
                )
                if test_config.is_crash_me:
                    print_info('ERROR', color='red')
                    raise TestsFailedError('Program has not crashed')
                print_info('OK', color='green')
            except TimeoutExpiredError:
                print_info('ERROR', color='red')
                message = f'Your solution exceeded time limit: {test_config.timeout} seconds'
                raise TestsFailedError(message)
            except ExecutionFailedError:
                if not test_config.is_crash_me:
                    print_info('ERROR', color='red')
                    raise TestsFailedError("Test failed (wrong answer or sanitizer error)")
            finally:
                if stdin is not None:
                    stdin.close()
        if test_config.is_crash_me:
            print_info('Program has crashed', color='green')
        else:
            print_info('All tests passed', color='green')
        return 1.
