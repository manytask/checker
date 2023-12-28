from __future__ import annotations

import os
from pathlib import Path

from .base import PluginOutput
from .scripts import RunScriptPlugin


HOME_PATH = str(Path.home())


class SafeRunScriptPlugin(RunScriptPlugin):
    """Wrapper over RunScriptPlugin to run students scripts safety.
    Plugin uses Firejail tool to create sandbox for the running process.
    He allows hide environment variables and control access to network and file system.
    """

    name = "safe_run_script"

    class Args(RunScriptPlugin.Args):
        allow_envs: set[str] = set()
        lock_network: bool = True
        allow_paths: set[str] = set()

    # TODO: at the moment "--queit" option of firejail may stil put extra strings in the output
    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        command = ["firejail", "--quiet", "--noprofile"]
        # lock network access
        if args.lock_network:
            command.append("--net=none")
        # collect all allow paths
        allow_paths = args.allow_paths.copy()
        allow_paths.add(args.origin)
        # a bit tricky but if paths is only /tmp add ~/tmp instead of it
        if "/tmp" in allow_paths and len(allow_paths) == 1:
            allow_paths.add("~/tmp")
        # remove /tmp from paths as it causes error inside of Firejail
        if "/tmp" in allow_paths:
            allow_paths.remove("/tmp")
        # replace ~ by the full home path
        for path in allow_paths:
            full_path = path if not path.startswith("~") else HOME_PATH + path[1:]
            # allow access to origin dir
            command.append(f"--whitelist={full_path}")
        # hide all environment variables
        command.append("env -i")
        for env in args.allow_envs:
            command.append(f'{env}="{os.environ.get(env, "")}"')
        if isinstance(args.script, str):
            command.append(args.script)
        else:
            assert isinstance(args.script, list)
            command.extend(args.script)
        run_args = RunScriptPlugin.Args(
            origin=args.origin, script=" ".join(command), timeout=args.timeout
        )

        return super()._run(args=run_args, verbose=verbose)
