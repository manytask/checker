from __future__ import annotations

import grp
import io
import os
import pwd
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

try:
    import unshare
except ImportError:
    unshare = None

from ..exceptions import ExecutionFailedError, TimeoutExpiredError
from ..utils.print import print_info


class Sandbox:
    ENV_WHITELIST = ['PATH']

    def __init__(
            self,
            *,
            dry_run: bool = False,
    ) -> None:
        self.dry_run = dry_run

    def _execute_external(
            self,
            command: str | list[str],
            *,
            capture_output: bool = False,
            verbose: bool = False,
            **kwargs: Any,
    ) -> str | None:
        if verbose or self.dry_run:
            if isinstance(command, str):
                cmdline = command
            else:
                cmdline = ' '.join(command)
            if 'preexec_fn' in kwargs:
                cmdline = 'sandbox ' + cmdline
            if 'cwd' in kwargs:
                cmdline = f'cd {kwargs["cwd"]} && {cmdline}'
            print_info('$', cmdline, color='grey')
            print_info('  execution kwargs: ', kwargs, color='grey')

        if self.dry_run:
            return None

        kwargs['check'] = kwargs.get('check', True)  # set check if missing
        try:
            if capture_output:
                start_time = time.monotonic()
                completed_process = subprocess.run(
                    command,
                    close_fds=False,
                    encoding='utf-8',
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # https://docs.python.org/3/library/subprocess.html -> capture_output
                    **kwargs
                )
                elapsed_time_seconds = time.monotonic() - start_time
                timeout_msg = ''
                if verbose and 'timeout' in kwargs:
                    timeout_msg = f'\nElapsed time is {elapsed_time_seconds:.2f} ' \
                                  f'with a limit of {kwargs["timeout"]:.0f} seconds\n'
                if completed_process.stdout:
                    return completed_process.stdout + timeout_msg
                return None
            else:
                start_time = time.monotonic()
                subprocess.run(
                    command,
                    close_fds=False,
                    **kwargs
                )
                elapsed_time_seconds = time.monotonic() - start_time
                if verbose and 'timeout' in kwargs:
                    print_info(f'Elapsed time is {elapsed_time_seconds:.2f} '
                               f'with a limit of {kwargs["timeout"]:.0f} seconds')
                return None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            timeout_msg = ''
            if isinstance(e, subprocess.TimeoutExpired):
                timeout_msg = f'Your solution exceeded time limit: {kwargs["timeout"]} seconds'
                if not capture_output:
                    print_info(timeout_msg, color='red')

            output = e.output or ''
            output = output if isinstance(output, str) else output.decode('utf-8')
            output = output + timeout_msg if capture_output else None
            if isinstance(e, subprocess.TimeoutExpired):
                raise TimeoutExpiredError(output=output) from e
            else:
                raise ExecutionFailedError(output=output) from e

    def _execute_callable(
            self,
            command: Callable[..., Any],
            *,
            capture_output: bool = False,
            verbose: bool = False,
            **kwargs: Any,
    ) -> str | None:
        if verbose or self.dry_run:
            args = ', '.join(f'{k}={repr(v)}' for k, v in sorted(kwargs.items()))
            print_info(f'> {command.__name__}({args})', color='grey')

        if self.dry_run:
            return None

        if capture_output:
            f = io.StringIO()
            with redirect_stdout(f), redirect_stderr(sys.stdout):
                command(**kwargs)
            return f.getvalue()
        else:
            command(**kwargs)
            return None

    def __call__(
            self,
            command: str | list[str] | Callable[..., Any],
            *,
            timeout: float | None = None,
            sandbox: bool = False,
            env_sandbox: bool = False,
            capture_output: bool = False,
            verbose: bool = False,
            **kwargs: Any,
    ) -> str | None:
        if isinstance(command, list) or isinstance(command, str):

            def set_up_env_sandbox() -> None:  # pragma: nocover
                env = os.environ.copy()
                os.environ.clear()
                for variable in self.ENV_WHITELIST:
                    os.environ[variable] = env[variable]

            def set_up_sandbox() -> None:  # pragma: nocover
                set_up_env_sandbox()

                # if unshare:
                #     try:
                #         unshare.unshare(unshare.CLONE_NEWNET)
                #         subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
                #     except Exception as e:
                #         print_info('WARNING: unable to create new net namespace, running with current one')
                #         if verbose:
                #             print_info(e.__class__.__name__, e)
                # else:
                #     print_info('WARNING: unshare is not installed, running without ip namespace')

                try:
                    uid = pwd.getpwnam('nobody').pw_uid
                    gid = grp.getgrnam('nogroup').gr_gid
                    os.setgroups([])
                    if sys.platform.startswith('linux'):
                        os.setresgid(gid, gid, gid)
                        os.setresuid(uid, uid, uid)
                except Exception as e:
                    print_info('WARNING: UID and GID change failed, running with current user')
                    if verbose:
                        print_info(e.__class__.__name__, e)

                set_up_env_sandbox()

            if env_sandbox:
                kwargs['preexec_fn'] = set_up_env_sandbox
            if sandbox:
                kwargs['preexec_fn'] = set_up_sandbox
            if timeout is not None:
                kwargs['timeout'] = timeout
            return self._execute_external(command, capture_output=capture_output, verbose=verbose, **kwargs)
        elif callable(command):
            if env_sandbox or sandbox or timeout:
                print_info('WARNING: env_sandbox, sandbox and timeout unavailable for callable execution, skip it')
            return self._execute_callable(command, capture_output=capture_output, verbose=verbose, **kwargs)
