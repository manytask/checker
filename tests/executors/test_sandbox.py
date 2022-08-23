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
    def test_dry_run(self, capsys: pytest.CaptureFixture[str]) -> None:
        sandbox = Sandbox(dry_run=True)

        failed_command_never_execute = 'false'
        sandbox(failed_command_never_execute)

        captured = capsys.readouterr()
        assert len(captured.out) + len(captured.err) > 0
        assert failed_command_never_execute in (captured.out + captured.err)

    def test_verbose(self, capsys: pytest.CaptureFixture[str]) -> None:
        sandbox = Sandbox()

        simple_command = 'true'
        sandbox(simple_command, verbose=True)

        captured = capsys.readouterr()
        assert len(captured.out) + len(captured.err) > 0
        assert simple_command in (captured.out + captured.err)

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

    def test_sandbox_blocks_env(self) -> None:
        sandbox = Sandbox()

        # test clear all not allowed variables
        os.environ['NOT_EXISTED_VAR_123'] = 'true'
        cmd_assert_blacklist_env_not_exists = '[ -z "${NOT_EXISTED_VAR_123}" ]'
        cmd_assert_blacklist_env_exists = '[ ! -z "${NOT_EXISTED_VAR_123}" ]'

        sandbox(cmd_assert_blacklist_env_not_exists, env_sandbox=True, shell=True)
        sandbox(cmd_assert_blacklist_env_not_exists, sandbox=True, shell=True)
        sandbox(cmd_assert_blacklist_env_exists, env_sandbox=False, shell=True)

        del os.environ['NOT_EXISTED_VAR_123']

        # test not clear allowed other variables
        if 'PATH' not in os.environ:
            os.environ['PATH'] = 'true'
        cmd_assert_whitelist_env_not_exists = '[ -z "${PATH}" ]'
        cmd_assert_whitelist_env_exists = '[ ! -z "${PATH}" ]'

        sandbox(cmd_assert_whitelist_env_exists, env_sandbox=True, shell=True)
        sandbox(cmd_assert_whitelist_env_exists, sandbox=True, shell=True)
        with pytest.raises(ExecutionFailedError):
            sandbox(cmd_assert_whitelist_env_not_exists, env_sandbox=False, shell=True)

        if os.environ['PATH'] == 'true':
            del os.environ['PATH']

    @skip_without_unshare
    def test_sandbox_blocks_web(self) -> None:
        sandbox = Sandbox()

        command_ping = ['ping', '-c 2', 'google.com.']
        with pytest.raises(ExecutionFailedError):
            sandbox(command_ping, sandbox=True)

    def test_timeout(self) -> None:
        sandbox = Sandbox()

        timeout_command = 'sleep 0.5'
        with pytest.raises(ExecutionFailedError):
            sandbox(timeout_command, timeout=0.2, shell=True)

    @pytest.mark.parametrize('command,output', [
        ('>&1 echo "std"', 'std\n'),
        ('>&2 echo "err"', 'err\n'),
        ('>&1 echo "std" && >&2 echo "err"', 'std\nerr\n'),
        ('>&1 echo "std1" && >&2 echo "err1" && >&1 echo "std2" && >&2 echo "err2"', 'std1\nerr1\nstd2\nerr2\n'),
    ])
    def test_output_catching_external(self, command: str, output: str) -> None:
        sandbox = Sandbox()

        assert sandbox(command, shell=True) is None

        assert sandbox(command, capture_output=True, shell=True) == output

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

    @pytest.mark.parametrize('command,output', [
        ('>&1 echo "std"', 'std\n'),
        ('>&2 echo "err"', 'err\n'),
        ('>&1 echo "std" && >&2 echo "err"', 'std\nerr\n'),
        ('>&1 echo "std1" && >&2 echo "err1" && >&1 echo "std2" && >&2 echo "err2"', 'std1\nerr1\nstd2\nerr2\n'),
    ])
    def test_output_catching_while_error(self, command: str, output: str) -> None:
        sandbox = Sandbox()

        command += ' && false'

        with pytest.raises(ExecutionFailedError) as exc_info:
            sandbox(command, capture_output=True, shell=True)

        assert exc_info.value.output == output

    @pytest.mark.parametrize('command,output', [
        ('>&1 echo "std"', 'std\n'),
        ('>&2 echo "err"', 'err\n'),
        ('>&1 echo "std" && >&2 echo "err"', 'std\nerr\n'),
        ('>&1 echo "std1" && >&2 echo "err1" && >&1 echo "std2" && >&2 echo "err2"', 'std1\nerr1\nstd2\nerr2\n'),
    ])
    def test_output_catching_while_timeout(self, command: str, output: str) -> None:
        sandbox = Sandbox()

        command += ' && sleep 0.5'

        with pytest.raises(ExecutionFailedError) as exc_info:
            sandbox(command, capture_output=True, timeout=0.2, shell=True)

        assert output in exc_info.value.output
        assert 'exceeded time limit' in exc_info.value.output
