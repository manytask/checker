import codecs
import re
import shutil
import tempfile
from pathlib import Path
from typing import Pattern
from dataclasses import dataclass

from .course import Task
from .executor import Executor, ExecutionFailedError
from .utils import print_info

IGNORE_FILE_PATTERNS = ['*.md', 'build', '__pycache__', '.pytest_cache']
TIMEOUT_SECS = 60


@dataclass
class ChecksFailedError(Exception):
    msg: str = ''
    output: str = ''

    def __repr__(self):
        return f'ChecksFailedError: {self.msg}'


@dataclass
class BuildFailedError(Exception):
    msg: str = ''
    output: str = ''

    def __repr__(self):
        return f'ChecksFailedError: {self.msg}'


class Tester:
    def __init__(self, cleanup: bool = True, dry_run: bool = False):
        self.cleanup = cleanup
        self.dry_run = dry_run
        self._executor = Executor(dry_run=dry_run)

        # self._build_dir = Path(tempfile.mkdtemp())
        # self._build_dir.chmod(0o777)  # Set mode for build directory (for code generation and so on)

    # def __del__(self):
    #     if self.cleanup and self._build_dir.exists():
    #         shutil.rmtree(self._build_dir)

    @staticmethod
    def _check_regexp(filename: Path, regexps: list[str]) -> None:
        file_content = codecs.open(filename, encoding='utf-8').read()
        for regexp in regexps:
            if re.search(regexp, file_content, re.MULTILINE):
                raise ValueError(f'File {filename} contains banned regexp "{regexp}"')

    @staticmethod
    def _copy_files(
            source: Path, target: Path,
            patterns: list[str] = None, ignore_patterns: list[str] = None,
            regex_check: bool = True,
            forbidden_regexp: list[Pattern] = None,
    ):
        forbidden_regexp = forbidden_regexp or []
        target.mkdir(parents=True, exist_ok=True)

        ignore_files = sum([
            list(source.glob(ignore_pattern))
            for ignore_pattern in (ignore_patterns or [])
        ], [])
        for pattern in (patterns or ['*']):
            for file in source.glob(pattern):
                if file in ignore_files:
                    continue
                source_path = source / file.name
                target_path = target / file.name
                if file.is_dir():
                    Tester._copy_files(
                        source_path, target_path,
                        patterns=['*'],
                        ignore_patterns=ignore_patterns,
                        regex_check=regex_check,
                        forbidden_regexp=forbidden_regexp,
                    )
                    continue

                if regex_check and str(source_path).endswith('.py'):
                    Tester._check_regexp(filename=source_path, regexps=forbidden_regexp)
                shutil.copyfile(str(source_path), str(target_path))

    def _gen_build(self, task: Task, source_path: Path, sandbox: bool = True, verbose: bool = False, normalize_output: bool = False) -> Path:
        # task_build_dir = Path(tempfile.mkdtemp(dir=self._build_dir))  # TODO: check why deleting
        task_build_dir = Path(tempfile.mkdtemp())
        task_build_dir.chmod(0o777)  # Set mode for build directory (for code generation and so on)

        # Copy submitted code (ignore tests)
        self._executor(
            self._copy_files, source=source_path, target=task_build_dir,
            ignore_patterns=task.config.test_files + IGNORE_FILE_PATTERNS, verbose=verbose
        )

        # Install submitted code as module if needed
        if task.config.module_test:
            # assert setup files exists
            setup_files = [i.name for i in task_build_dir.glob(r'setup.*')]
            if 'setup.py' not in setup_files and 'setup.cfg' not in setup_files:
                raise BuildFailedError('This task is in editable `module` mode. You have to provide setup.cfg/setup.py file')
            if 'setup.py' not in setup_files:
                raise BuildFailedError('This task is in editable `module` mode. You have to provide setup.py file')

            if task.config.build_wheel:
                task_build_dir_dist = task_build_dir / 'dist'
                output = self._executor(
                    ['pip3', 'wheel', '--wheel-dir', str(task_build_dir_dist), str(task_build_dir)],
                    verbose=verbose,
                    env_sandbox=sandbox,
                    capture_output=normalize_output,
                )
                if normalize_output:
                    print_info(output or '', end='')

                output = self._executor(
                    ['pip3', 'install', '--prefer-binary', '--force-reinstall', '--find-links', str(task_build_dir_dist), str(task_build_dir)],
                    verbose=verbose,
                    env_sandbox=sandbox,
                    capture_output=normalize_output,
                )
                if normalize_output:
                    print_info(output or '', end='')
            else:
                output = self._executor(
                    ['pip3', 'install', '-e', str(task_build_dir), '--force'],
                    verbose=verbose,
                    env_sandbox=sandbox,
                    capture_output=normalize_output,
                )
                if normalize_output:
                    print_info(output or '', end='')

        # Copy public test files
        self._executor(
            self._copy_files, source=task.public_dir, target=task_build_dir,
            patterns=task.config.public_test_files, regex_check=False, verbose=verbose
        )

        # Copy private test files
        self._executor(
            self._copy_files, source=task.private_dir, target=task_build_dir,
            patterns=task.config.private_test_files, regex_check=False, verbose=verbose
        )

        return task_build_dir

    def _clean_build(self, build_dir: Path, verbose: bool = False):
        self._executor(['rm', '-rf', str(build_dir)], check=False, verbose=verbose)

    @staticmethod
    def _parse_summary_score(output: str):
        score = 0
        for line in output.splitlines():
            if 'Summary score is: ' in line:
                score += float(line.strip().split('Summary score is: ')[1])
        return round(score)

    def _run_tests(self, task: Task, build_dir: Path, sandbox: bool = False, verbose: bool = False,
                   normalize_output: bool = False) -> int:
        # TODO: replace with preserved setup.cfg
        codestyle_cmd = [
            'flake8',
            '--exclude', ','.join(task.config.private_test_files),
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
            # '--disable-socket', '--allow-unix-socket',
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
            # '--disable-socket', '--allow-unix-socket',
            str(build_dir)
        ]
        if not verbose:
            tests_cmd += ['--no-header']
        if not verbose and not task.config.verbose_tests_output:
            tests_cmd += ['--tb=no']
        # if task.config.partially_scored:
        #     tests_cmd += ['-s']
        if task.config.coverage:
            tests_cmd += ['--cov-report', 'term-missing']

            # exclude test files
            dirs_to_cover = {
                i.relative_to(build_dir) for i in build_dir.iterdir()
                if i.suffix in ['', '.py'] and i.name not in task.config.test_files and i.name != 'setup.py'
            }
            if dirs_to_cover:
                for _dir in dirs_to_cover:
                    _dir = str(_dir).replace(r'.', r'\.')
                    tests_cmd += ['--cov', str(_dir)]
            else:
                tests_cmd += ['--cov', str(build_dir)]

            # tests_cmd += ['--cov-config', '.coveragerc']
            if task.config.coverage is not True:
                tests_cmd += ['--cov-fail-under', str(task.config.coverage)]
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
        except ExecutionFailedError as err:
            # Always reraise for style checks
            styles_err = err

            if normalize_output:
                print_info(err.output, end='')
                err.output = ''
            print_info('ERROR', color='red')

        # Check typing
        typing_err = None
        try:
            if task.config.run_mypy:
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
        except ExecutionFailedError as err:
            # Always reraise for typing checks
            typing_err = err

            if normalize_output:
                print_info(err.output, end='')
                err.output = ''
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
        except ExecutionFailedError as err:
            # Always reraise for import checks
            import_err = err

            if normalize_output:
                print_info(err.output, end='')
                err.output = ''
            print_info('ERROR', color='red')

        # Check tests
        tests_err = None
        try:
            print_info('Running tests...', color='orange')
            output = self._executor(
                tests_cmd,
                sandbox=sandbox,
                cwd=str(build_dir),
                timeout=task.config.test_timeout if task.config.test_timeout else TIMEOUT_SECS,
                verbose=verbose,
                capture_output=task.config.partially_scored or normalize_output,
            )
            if normalize_output or task.config.partially_scored:
                print_info(output, end='')
            print_info('OK', color='green')
        except ExecutionFailedError as err:
            if not task.config.partially_scored:
                # Reraise only if all tests should pass
                tests_err = err
            output = err.output

            if normalize_output or task.config.partially_scored:
                print_info(output, end='')

            if task.config.partially_scored:
                print_info('ERROR? (Some tests failed, but this is partially_scored task)', color='orange')
            else:
                print_info('ERROR', color='red')

        if import_err is not None:
            raise ChecksFailedError('Import error', output=import_err.output) from import_err

        if tests_err is not None:
            raise ChecksFailedError('Public or private tests error', output=tests_err.output) from tests_err

        if styles_err is not None:
            raise ChecksFailedError('Style error', output=styles_err.output) from styles_err

        if typing_err is not None:
            raise ChecksFailedError('Typing error', output=typing_err.output) from typing_err

        if task.config.partially_scored:
            return self._parse_summary_score(output)
        else:
            return task.max_score

    def run_tests(self, task: Task, source_path: Path, verbose: bool = False, normalize_output: bool = False) -> int:
        try:
            build_dir = self._gen_build(task, source_path, sandbox=True, verbose=verbose, normalize_output=normalize_output)
        except BuildFailedError as e:
            print_info('\nOoops... Something went wrong: ' + e.msg, color='red')
            raise e
        try:
            # Do not disable sandbox (otherwise it will not clear environ,
            # so environ-related issues may be missed, such as empty locale)
            score = self._run_tests(task, build_dir, sandbox=True, verbose=verbose, normalize_output=normalize_output)
        except ChecksFailedError as e:
            print_info('\nOoops... Something went wrong: ' + e.msg, color='red')
            raise e
        finally:
            if self.cleanup:
                self._clean_build(build_dir, verbose=verbose)
            else:
                print_info(f'Keeping build directory: {build_dir}')

        return score
