from __future__ import annotations

import re
from dataclasses import InitVar, dataclass, field
from pathlib import Path

from ..exceptions import BuildFailedError, ExecutionFailedError, RunFailedError, StylecheckFailedError, TestsFailedError
from ..utils.files import check_folder_contains_regexp, copy_files
from ..utils.print import print_info
from .tester import Tester

IGNORE_FILE_PATTERNS = ['*.md', 'build', '__pycache__', '.pytest_cache', '.mypy_cache']
COVER_IGNORE_FILES = ['setup.py']


class PythonTester(Tester):

    SOURCE_FILES_EXTENSIONS: list[str] = ['.py']

    @dataclass
    class TaskTestConfig(Tester.TaskTestConfig):
        partially_scored: bool = False
        verbose_tests_output: bool = False
        module_test: bool = False
        build_wheel: bool = False
        run_mypy: bool = True

        forbidden_regexp: list[re.Pattern[str]] = field(default_factory=list)

        public_test_files: list[str] = field(default_factory=list)
        private_test_files: list[str] = field(default_factory=list)

        test_timeout: int = 60  # seconds
        coverage: bool | int = False

        # Created on init
        test_files: list[str] = field(init=False, default_factory=list)
        # Init only
        explicit_public_tests: InitVar[list[str]] = None
        explicit_private_tests: InitVar[list[str]] = None

        def __post_init__(
                self,
                explicit_public_tests: list[str] | None,
                explicit_private_tests: list[str] | None,
        ) -> None:
            self.forbidden_regexp += [r'exit\(0\)']  # type: ignore
            for regexp in self.forbidden_regexp:
                re.compile(regexp)

            self.public_test_files = ['test_public.py'] + (explicit_public_tests or [])
            self.private_test_files = ['test_private.py'] + (explicit_private_tests or [])
            self.test_files = self.public_test_files + self.private_test_files

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
        # Copy submitted code (ignore tests)
        self._executor(
            copy_files,
            source=source_dir,
            target=build_dir,
            ignore_patterns=test_config.test_files + IGNORE_FILE_PATTERNS,
            verbose=verbose,
        )

        # Check submitted code using forbidden regexp
        self._executor(
            check_folder_contains_regexp,
            folder=build_dir,
            extensions=self.SOURCE_FILES_EXTENSIONS,
            regexps=test_config.forbidden_regexp,
            raise_on_found=True,
            verbose=verbose,
        )

        # Install submitted code as module if needed
        if test_config.module_test:
            # assert setup files exists
            setup_files = {i.name for i in build_dir.glob(r'setup.*')} | \
                          {i.name for i in build_dir.glob(r'pyproject.*')}
            if 'setup.py' not in setup_files and 'setup.cfg' not in setup_files and 'pyproject.toml' not in setup_files:
                raise BuildFailedError(
                    'This task is in editable `module` mode. You have to provide pyproject.toml/setup.cfg/setup.py file'
                )
            if 'setup.py' not in setup_files:
                raise BuildFailedError('This task is in editable `module` mode. You have to provide setup.py file')

            if test_config.build_wheel:
                task_build_dir_dist = build_dir / 'dist'
                output = self._executor(
                    ['pip3', 'wheel', '--wheel-dir', str(task_build_dir_dist), str(build_dir)],
                    verbose=verbose,
                    env_sandbox=sandbox,
                    capture_output=normalize_output,
                )
                if normalize_output:
                    print_info(output or '', end='')

                output = self._executor(
                    ['pip3', 'install', '--prefer-binary', '--force-reinstall', '--find-links',
                     str(task_build_dir_dist), str(build_dir)],
                    verbose=verbose,
                    env_sandbox=sandbox,
                    capture_output=normalize_output,
                )
                if normalize_output:
                    print_info(output or '', end='')

                if (build_dir / 'build').exists():
                    output = self._executor(
                        ['rm', '-rf', str(build_dir / 'build')],
                        verbose=verbose,
                        env_sandbox=sandbox,
                        capture_output=normalize_output,
                    )
                    if normalize_output:
                        print_info(output or '', end='')
            else:
                output = self._executor(
                    ['pip3', 'install', '-e', str(build_dir), '--force'],
                    verbose=verbose,
                    env_sandbox=sandbox,
                    capture_output=normalize_output,
                )
                if normalize_output:
                    print_info(output or '', end='')

        # Copy public test files
        self._executor(
            copy_files,
            source=public_tests_dir,
            target=build_dir,
            patterns=test_config.public_test_files,
            verbose=verbose,
        )

        # Copy private test files
        self._executor(
            copy_files,
            source=private_tests_dir,
            target=build_dir,
            patterns=test_config.private_test_files,
            verbose=verbose,
        )

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

    @staticmethod
    def _parse_summary_score(
            output: str,
    ) -> float:
        score = 0.0
        for line in output.splitlines():
            if 'Summary score percentage is: ' in line:
                score += float(line.strip().split('Summary score percentage is: ')[1])
                break
        return score

    def _run_tests(  # type: ignore[override]
            self,
            test_config: TaskTestConfig,
            build_dir: Path,
            sandbox: bool = False,
            verbose: bool = False,
            normalize_output: bool = False,
    ) -> float:
        # TODO: replace with preserved setup.cfg
        codestyle_cmd = [
            'flake8',
            '--exclude', ','.join(test_config.private_test_files),
            '--max-line-length', '120',
            str(build_dir)
        ]
        mypy_cmd = [
            'mypy',
            '--no-incremental',
            '--cache-dir', '/dev/null',
            '--ignore-missing-imports',
            '--disallow-untyped-defs',
            '--disallow-incomplete-defs',
            '--disallow-subclassing-any',
            '--disallow-any-generics',
            '--no-implicit-optional',
            '--warn-redundant-casts',
            '--warn-unused-ignores',
            '--warn-unreachable',
            '--allow-untyped-decorators',
            str(build_dir)
        ]
        tests_collection_cmd = [
            'pytest',
            '-p', 'no:cacheprovider',
            '-p', 'no:requests_mock',
            '-p', 'no:cov',
            '-p', 'no:mock',
            '-p', 'no:socket',
            '-qq',
            '--collect-only',
            str(build_dir)
        ]
        tests_cmd = [
            'pytest',
            '-p', 'no:cacheprovider',
            '-p', 'no:requests_mock',
            '-p', 'no:timeout',
            '-p', 'no:socket',
            # '--timeout=60',
            str(build_dir)
        ]
        if not verbose:
            tests_cmd += ['--no-header']
        if not verbose and not test_config.verbose_tests_output:
            tests_cmd += ['--tb=no']
        # if test_config.partially_scored:
        #     tests_cmd += ['-s']
        if test_config.coverage:
            tests_cmd += ['--cov-report', 'term-missing']

            # exclude test files
            dirs_to_cover = {
                i.relative_to(build_dir) for i in build_dir.iterdir()
                if i.suffix in ['', '.py'] and i.name not in test_config.test_files and i.name not in COVER_IGNORE_FILES
            }
            if dirs_to_cover:
                for _dir in dirs_to_cover:
                    tests_cmd += ['--cov', str(_dir).replace(r'.', r'\.')]
            else:
                tests_cmd += ['--cov', str(build_dir)]

            # tests_cmd += ['--cov-config', '.coveragerc']
            if test_config.coverage is not True:
                tests_cmd += ['--cov-fail-under', str(test_config.coverage)]
        else:
            tests_cmd += ['-p', 'no:cov']

        # Check style
        styles_err = None
        try:
            print_info('Running codestyle checks...', color='orange')
            output = self._executor(
                codestyle_cmd,
                sandbox=sandbox,
                cwd=str(build_dir),
                verbose=verbose,
                capture_output=normalize_output,
            )
            if normalize_output:
                print_info(output or '', end='')
            print_info('[No issues]')
            print_info('OK', color='green')
        except ExecutionFailedError as e:
            # Always reraise for style checks
            styles_err = e

            if normalize_output:
                print_info(e.output, end='')
                e.output = ''
            print_info('ERROR', color='red')

        # Check typing
        typing_err = None
        try:
            if test_config.run_mypy:
                print_info('Running mypy checks...', color='orange')
                output = self._executor(
                    mypy_cmd,
                    sandbox=sandbox,
                    cwd=str(build_dir.parent),  # mypy didn't work from cwd
                    verbose=verbose,
                    capture_output=normalize_output,
                )
                if normalize_output:
                    print_info(output, end='')
                print_info('OK', color='green')
            else:
                print_info('Type check is skipped for this task!', color='orange')
        except ExecutionFailedError as e:
            # Always reraise for typing checks
            typing_err = e

            if normalize_output:
                print_info(e.output, end='')
                e.output = ''
            print_info('ERROR', color='red')

        # Check import and tests collecting
        import_err = None
        try:
            print_info('Collecting tests...', color='orange')
            output = self._executor(
                tests_collection_cmd,
                sandbox=sandbox,
                cwd=str(build_dir),
                verbose=verbose,
                capture_output=normalize_output,
            )
            if normalize_output:
                print_info(output, end='')
            print_info('OK', color='green')
        except ExecutionFailedError as e:
            # Always reraise for import checks
            import_err = e

            if normalize_output:
                print_info(e.output, end='')
                e.output = ''
            print_info('ERROR', color='red')

        # Check tests
        tests_err = None
        try:
            print_info('Running tests...', color='orange')
            output = self._executor(
                tests_cmd,
                sandbox=sandbox,
                cwd=str(build_dir),
                timeout=test_config.test_timeout,
                verbose=verbose,
                capture_output=test_config.partially_scored or normalize_output,
            )
            if normalize_output or test_config.partially_scored:
                print_info(output, end='')
            print_info('OK', color='green')
        except ExecutionFailedError as e:
            if not test_config.partially_scored:
                # Reraise only if all tests should pass
                tests_err = e
            output = e.output

            if normalize_output or test_config.partially_scored:
                print_info(output, end='')

            if test_config.partially_scored:
                print_info('ERROR? (Some tests failed, but this is partially_scored task)', color='orange')
            else:
                print_info('ERROR', color='red')

        if import_err is not None:
            raise RunFailedError('Import error', output=import_err.output) from import_err

        if tests_err is not None:
            raise TestsFailedError('Public or private tests error', output=tests_err.output) from tests_err

        if styles_err is not None:
            raise StylecheckFailedError('Style error', output=styles_err.output) from styles_err

        if typing_err is not None:
            raise StylecheckFailedError('Typing error', output=typing_err.output) from typing_err

        if test_config.partially_scored:
            output = output or ''  # for mypy only
            return self._parse_summary_score(output)
        else:
            return 1.
