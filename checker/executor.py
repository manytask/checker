import grp
import os
import pwd
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

try:
    import unshare
except ImportError:
    unshare = None

from .utils import print_info


EXECUTOR_ENV_WHITELIST = ['PATH']


@dataclass
class ExecutionFailedError(Exception):
    output: str


class Executor:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def _execute_external(
            self, command,
            capture_output: bool = False,
            verbose: bool = False,
            **kwargs
        ):
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
            return

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
                    timeout_msg = f'\nElapsed time is {elapsed_time_seconds:.2f} with a limit of {kwargs["timeout"]:.0f} seconds\n'
                if completed_process.stderr or completed_process.stdout:
                    return (str(completed_process.stderr) or '') + (str(completed_process.stdout) or '') + timeout_msg
                return None
            else:
                start_time = time.monotonic()
                subprocess.run(command, close_fds=False, **kwargs)
                elapsed_time_seconds = time.monotonic() - start_time
                if verbose and 'timeout' in kwargs:
                    print_info(f'Elapsed time is {elapsed_time_seconds:.2f} with a limit of {kwargs["timeout"]:.0f} seconds')
                return None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
            if isinstance(err, subprocess.TimeoutExpired):
                print_info(f'Your solution exceeded time limit: {kwargs["timeout"]} seconds', color='red')
            raise ExecutionFailedError(output=(str(err.stderr) or '') + (str(err.stdout) or '') if capture_output else None) from err

    def _execute_callable(self, command, verbose: bool = False, **kwargs):
        if verbose or self.dry_run:
            args = ', '.join(f'{k}={repr(v)}' for k, v in sorted(kwargs.items()))
            print_info(f'> {command.__name__}({args})', color='grey')

        if self.dry_run:
            return

        command(**kwargs)

    def __call__(
            self, command,
            timeout: Optional[int] = None,
            sandbox: bool = False,
            env_sandbox: bool = False,
            verbose: bool = False,
            **kwargs
        ):
        if isinstance(command, list) or isinstance(command, str):

            def set_up_env_sandbox():
                env = os.environ.copy()
                os.environ.clear()
                for variable in EXECUTOR_ENV_WHITELIST:
                    os.environ[variable] = env[variable]

            def set_up_sandbox():
                set_up_env_sandbox()

                try:
                    unshare.unshare(unshare.CLONE_NEWNET)
                    subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
                except Exception:
                    print_info('WARNING: unable to create new net namespace, running with current one')

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
