from __future__ import annotations

import subprocess
from pathlib import Path

from checker.exceptions import PluginExecutionFailed
from checker.plugins.cpp.blacklist import get_cpp_blacklist
from checker.plugins.firejail import SafeRunScriptPlugin
from checker.utils import print_info

from .base import PluginABC, PluginOutput


class CppCrashMePlugin(PluginABC):
    name = "cpp_crash_me"

    class Args(PluginABC.Args):
        reference_root: Path
        task_path: Path
        binary_name: str
        script: list[str]

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        if not args.binary_name:
            raise PluginExecutionFailed(output="Wrong binary name")
        if not args.script:
            raise PluginExecutionFailed(output="Wrong script")

        script = args.script + [args.binary_name]
        print_info(" ".join(script))

        run_args = SafeRunScriptPlugin.Args(
            origin=str(args.task_path),
            script=script,
            env_whitelist=["PATH"],
            paths_blacklist=get_cpp_blacklist(args.reference_root),
        )
        output = SafeRunScriptPlugin()._run(run_args, verbose=verbose).output
        if output:
            print_info(output)

        input = args.task_path / "input.txt"
        run_args = SafeRunScriptPlugin.Args(
            origin=str(args.task_path),
            script=["./" + args.binary_name],
            input=input,
            env_whitelist=[str(input)],
            paths_blacklist=get_cpp_blacklist(args.reference_root),
        )
        print_info(f"./{args.binary_name} < input.txt")

        crashed = False
        crash_message = ""
        try:
            SafeRunScriptPlugin()._run(run_args, verbose=verbose)
        except PluginExecutionFailed as e:
            if type(e.__context__) is subprocess.CalledProcessError:
                crashed = True
                crash_message = e.message

        run_args = SafeRunScriptPlugin.Args(
            origin=str(args.task_path),
            script=["rm", args.binary_name],
            paths_blacklist=get_cpp_blacklist(args.reference_root),
        )
        SafeRunScriptPlugin()._run(run_args, verbose=verbose)

        if crashed:
            return PluginOutput(output=crash_message)
        else:
            raise PluginExecutionFailed(output="Program has not crashed")
