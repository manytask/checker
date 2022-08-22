import os
import sys
from pathlib import Path

import pytest

from checker.exceptions import ExecutionFailedError

try:
    import unshare
except ImportError:
    unshare = None

from checker.executors.sandbox import Sandbox

skip_without_unshare = pytest.mark.skipif(
    unshare is None, reason='unshare lib is unavailable'
)


class TestSandbox:
    def test_execute_external_str(self, tmp_path: Path) -> None:
        sandbox = Sandbox()

        tmp_file = tmp_path / 'test.tmp'

        create_file = f'touch {tmp_file.as_posix()}'

        sandbox(create_file, shell=True)
        assert tmp_file.exists()

    def test_execute_external_list(self, tmp_path: Path) -> None:
        sandbox = Sandbox()

        tmp_file = tmp_path / 'test.tmp'

        create_file = ['touch', str(tmp_file.as_posix())]

        sandbox(create_file)
        assert tmp_file.exists()

    def test_execute_callable(self, tmp_path: Path) -> None:
        sandbox = Sandbox()

        tmp_file = tmp_path / 'test.tmp'

        def create_file() -> None:
            tmp_file.touch()

        sandbox(create_file)
        assert tmp_file.exists()

    def test_env_sandbox(self) -> None:
        sandbox = Sandbox()

        # test clear all not allowed variables
        os.environ['NOT_EXISTED_VAR_123'] = 'true'
        cmd_assert_blacklist_env_not_exists = '[ -z "${NOT_EXISTED_VAR_123}" ]'
        cmd_assert_blacklist_env_exists = '[ ! -z "${NOT_EXISTED_VAR_123}" ]'

        sandbox(cmd_assert_blacklist_env_not_exists, env_sandbox=True, shell=True)
        sandbox(cmd_assert_blacklist_env_exists, env_sandbox=False, shell=True)

        del os.environ['NOT_EXISTED_VAR_123']

        # test not clear allowed other variables
        if 'PATH' not in os.environ:
            os.environ['PATH'] = 'true'
        cmd_assert_whitelist_env_not_exists = '[ -z "${PATH}" ]'
        cmd_assert_whitelist_env_exists = '[ ! -z "${PATH}" ]'

        sandbox(cmd_assert_whitelist_env_exists, env_sandbox=True, shell=True)
        with pytest.raises(ExecutionFailedError):
            sandbox(cmd_assert_whitelist_env_not_exists, env_sandbox=False, shell=True)

        if os.environ['PATH'] == 'true':
            del os.environ['PATH']

    def test_sandbox(self) -> None:
        pass

    def test_timeout(self) -> None:
        sandbox = Sandbox()

        timeout_command = 'sleep 2'
        with pytest.raises(ExecutionFailedError):
            sandbox(timeout_command, timeout=1, shell=True)

    def test_output_catching_external(self) -> None:
        sandbox = Sandbox()

        assert sandbox('echo "std"', shell=True) is None

        assert sandbox('>&1 echo "std"', capture_output=True, shell=True) == 'std\n'

        assert sandbox('>&2 echo "error"', capture_output=True, shell=True) == 'error\n'

        assert sandbox(
            '>&1 echo "std" && >&2 echo "error"', capture_output=True, shell=True
        ) == 'std\nerror\n'

        assert sandbox(
            '>&1 echo "std1" && >&2 echo "error1" && >&1 echo "std2" && >&2 echo "error2"',
            capture_output=True, shell=True
        ) == 'std1\nerror1\nstd2\nerror2\n'

    def test_output_catching_callable(self) -> None:
        sandbox = Sandbox()

        def print_std() -> None:
            print('std')
        assert sandbox(print_std) is None
        assert sandbox(print_std, capture_output=True) == 'std\n'

        def print_error() -> None:
            print('error', file=sys.stderr)
        assert sandbox(print_error, capture_output=True) == 'error\n'

        def print_std_error() -> None:
            print('std')
            print('error', file=sys.stderr)
        assert sandbox(print_std_error, capture_output=True) == 'std\nerror\n'

        def print_std_error_complicated() -> None:
            print('std1')
            print('error1', file=sys.stderr)
            print('std2')
            print('error2', file=sys.stderr)
        assert sandbox(print_std_error_complicated, capture_output=True) == 'std1\nerror1\nstd2\nerror2\n'

