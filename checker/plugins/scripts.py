from __future__ import annotations

from pydantic import Field

from .base import PluginABC
from ..exceptions import ExecutionFailedError, ExecutionTimeoutError, RunFailedError


class RunScriptPlugin(PluginABC):
    """Plugin for running scripts."""

    name = "run_script"

    class Args(PluginABC.Args):
        origin: str
        script: str | list[str]
        timeout: int | None = None
        isolate: bool = False
        env_whitelist: list[str] = Field(default_factory=lambda: ['PATH'])

    def _run(self, args: Args, *, verbose: bool = False) -> str:
        import subprocess

        def set_up_env_sandbox() -> None:  # pragma: nocover
            import os
            env = os.environ.copy()
            os.environ.clear()
            for variable in args.env_whitelist:
                os.environ[variable] = env[variable]

        try:
            result = subprocess.run(
                args.script,
                shell=True,
                cwd=args.origin,
                timeout=args.timeout,  # kill process after timeout, raise TimeoutExpired
                check=True,  # raise CalledProcessError if return code is non-zero
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # merge stderr & stdout to single output
                preexec_fn=set_up_env_sandbox,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            output = e.output if isinstance(e.output, str) else e.output.decode('utf-8')

            if isinstance(e, subprocess.TimeoutExpired):
                raise ExecutionTimeoutError(
                    f"Script timed out after {e.timeout}s ({args.timeout}s limit)",
                    output=output,
                ) from e
            else:
                raise RunFailedError(
                    f"Script failed with exit code {e.returncode}",
                    output=output,
                ) from e

        return result.stdout.decode('utf-8')
