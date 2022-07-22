from __future__ import annotations

import grp
import os
import pwd
import subprocess
import time
from collections.abc import Callable
from typing import Any

try:
    import unshare
except ImportError:
    unshare = None

from .utils.print import print_info
from .exceptions import ExecutionFailedError


class Executor:
    EXECUTOR_ENV_WHITELIST = ['PATH']

    def __init__(self, dry_run: bool = False) -> None:
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
                    # stderr=subprocess.PIPE,
                    capture_output=True,
                    **kwargs
                )
                elapsed_time_seconds = time.monotonic() - start_time
                timeout_msg = ''
                if verbose and 'timeout' in kwargs:
                    timeout_msg = f'\nElapsed time is {elapsed_time_seconds:.2f} ' \
                                  f'with a limit of {kwargs["timeout"]:.0f} seconds\n'
                if completed_process.stderr or completed_process.stdout:
                    return (str(completed_process.stderr) or '') + (str(completed_process.stdout) or '') + timeout_msg
                return None
            else:
                start_time = time.monotonic()
                subprocess.run(command, close_fds=False, **kwargs)
                elapsed_time_seconds = time.monotonic() - start_time
                if verbose and 'timeout' in kwargs:
                    print_info(f'Elapsed time is {elapsed_time_seconds:.2f} '
                               f'with a limit of {kwargs["timeout"]:.0f} seconds')
                return None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            if isinstance(e, subprocess.TimeoutExpired):
                print_info(f'Your solution exceeded time limit: {kwargs["timeout"]} seconds', color='red')
            raise ExecutionFailedError(
                output=(str(e.stderr) or '') + (str(e.stdout) or '') if capture_output else None
            ) from e

    def _execute_callable(
            self,
            command: Callable[..., Any],
            *,
            verbose: bool = False,
            **kwargs: Any,
    ) -> str | None:
        if verbose or self.dry_run:
            args = ', '.join(f'{k}={repr(v)}' for k, v in sorted(kwargs.items()))
            print_info(f'> {command.__name__}({args})', color='grey')

        if self.dry_run:
            return None

        command(**kwargs)
        return None

    def __call__(
            self,
            command: str | list[str] | Callable[..., Any],
            *,
            timeout: int | None = None,
            sandbox: bool = False,
            env_sandbox: bool = False,
            verbose: bool = False,
            **kwargs: Any,
    ) -> str | None:
        if isinstance(command, list) or isinstance(command, str):

            def set_up_env_sandbox() -> None:
                env = os.environ.copy()
                os.environ.clear()
                for variable in self.EXECUTOR_ENV_WHITELIST:
                    os.environ[variable] = env[variable]

            def set_up_sandbox() -> None:
                set_up_env_sandbox()

                if not unshare:
                    print_info('WARNING: unshare is not installed')
                try:
                    unshare.unshare(unshare.CLONE_NEWNET)
                    subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
                except Exception as e:
                    print_info('WARNING: unable to create new net namespace, running with current one')
                    if verbose:
                        print_info(e)

                try:
                    uid = pwd.getpwnam('nobody').pw_uid
                    gid = grp.getgrnam('nogroup').gr_gid
                    os.setgroups([])
                    os.setresgid(gid, gid, gid)
                    os.setresuid(uid, uid, uid)
                except Exception:
                    print_info('WARNING: UID and GID change failed, running with current user')

                set_up_env_sandbox()

            if env_sandbox:
                kwargs['preexec_fn'] = set_up_env_sandbox
            if sandbox:
                kwargs['preexec_fn'] = set_up_sandbox
            if timeout is not None:
                kwargs['timeout'] = timeout
            return self._execute_external(command, verbose=verbose, **kwargs)
        elif callable(command):
            return self._execute_callable(command, verbose=verbose, **kwargs)
