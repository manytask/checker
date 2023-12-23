from __future__ import annotations

from typing import Union

from ..exceptions import PluginExecutionFailed
from .base import PluginABC, PluginOutput


class RunScriptPlugin(PluginABC):
    """Plugin for running scripts."""

    name = "run_script"

    class Args(PluginABC.Args):
        origin: str
        script: Union[str, list[str]]  # as pydantic does not support | in older python versions
        timeout: Union[float, None] = None  # as pydantic does not support | in older python versions

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        import subprocess

        try:
            result = subprocess.run(
                args.script,
                shell=True,
                cwd=args.origin,
                timeout=args.timeout,  # kill process after timeout, raise TimeoutExpired
                check=True,  # raise CalledProcessError if return code is non-zero
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # merge stderr & stdout to single output
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            output = e.output or ""
            output = output if isinstance(output, str) else output.decode("utf-8")

            if isinstance(e, subprocess.TimeoutExpired):
                raise PluginExecutionFailed(
                    f"Script timed out after {e.timeout}s ({args.timeout}s limit)",
                    output=output,
                ) from e
            else:
                raise PluginExecutionFailed(
                    f"Script failed with exit code {e.returncode}",
                    output=output,
                ) from e

        return PluginOutput(
            output=result.stdout.decode("utf-8"),
        )
