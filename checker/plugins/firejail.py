from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Union

from ..exceptions import PluginExecutionFailed
from .base import PluginOutput
from .scripts import PluginABC, RunScriptPlugin


HOME_PATH = str(Path.home())


class SafeRunScriptPlugin(PluginABC):
    """Wrapper over RunScriptPlugin to run students scripts safety.
    Plugin uses Firejail tool to create sandbox for the running process.
    It allows hide environment variables and control access to network and file system.
    If `allow_fallback=True` then if Firejail is not installed, it will fallback to RunScriptPlugin.
    """

    name = "safe_run_script"

    class Args(PluginABC.Args):
        origin: str
        script: Union[str, list[str]]  # as pydantic does not support | in older python versions
        timeout: Union[float, None] = None  # as pydantic does not support | in older python versions

        allow_envs: set[str] = set()
        lock_network: bool = True
        allow_paths: set[str] = set()
        allow_fallback: bool = False

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        # test if firejail script is available
        # TODO: test fallback
        result = subprocess.run(["firejail", "--version"], capture_output=True)
        if result.returncode != 0:
            if args.allow_fallback:
                # fallback to RunScriptPlugin
                run_args = RunScriptPlugin.Args(origin=args.origin, script=args.script, timeout=args.timeout)
                output = RunScriptPlugin()._run(args=run_args, verbose=verbose)
                if verbose:
                    output.output = f"Firejail is not installed. Fallback to RunScriptPlugin.\n{output.output}"
                return output
            else:
                # error
                raise PluginExecutionFailed("Firejail is not installed", output=result.stderr.decode("utf-8"))

        # Construct firejail command
        command: list[str] = ["firejail", "--quiet", "--noprofile"]

        # lock network access
        if args.lock_network:
            command.append("--net=none")

        # Collect all allow paths
        allow_paths = {*args.allow_paths, args.origin}
        # a bit tricky but if paths is only /tmp add ~/tmp instead of it
        if "/tmp" in allow_paths and len(allow_paths) == 1:
            allow_paths.add("~/tmp")
        # remove /tmp from paths as it causes error inside Firejail
        if "/tmp" in allow_paths:
            allow_paths.remove("/tmp")
        # replace ~ by the full home path
        for path in allow_paths:
            full_path = path if not path.startswith("~") else HOME_PATH + path[1:]
            # allow access to origin dir
            command.append(f"--whitelist={full_path}")

        # Hide all environment variables except allowed
        command.append("env -i")
        for env in args.allow_envs:
            command.append(f'{env}="{os.environ.get(env, "")}"')

        # create actual command
        run_command: str | list[str]
        if isinstance(args.script, str):
            run_command = " ".join(command) + " " + args.script
        elif isinstance(args.script, list):
            run_command = command + args.script
        else:
            assert False, "Now Reachable"

        # Will use RunScriptPlugin to run Firejail+command
        run_args = RunScriptPlugin.Args(origin=args.origin, script=run_command, timeout=args.timeout)
        return RunScriptPlugin()._run(args=run_args, verbose=verbose)
