from __future__ import annotations

from pathlib import Path

from checker.exceptions import PluginExecutionFailed
from checker.plugins.scripts import RunScriptPlugin
from checker.utils import print_info

from .base import PluginABC, PluginOutput


class CppForbiddenPlugin(PluginABC):
    name = "cpp_forbidden"

    class Args(PluginABC.Args):
        reference_root: Path
        task_path: Path
        allow_change: list[str] | str
        forbidden: list[str] = []
        forbidden_files: list[str] = []
        forbidden_checker: str

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        allow_change = args.allow_change
        if isinstance(allow_change, str):
            allow_change = [allow_change]

        files: list[str] = []
        for r in allow_change:
            files += list(map(str, args.task_path.glob(r)))
        files = list(set(files))

        forbidden: list[str] = []
        for f in args.forbidden:
            forbidden += ["-f", f]
        for f in args.forbidden_files:
            forbidden += ["-ff", f]

        checker_args = forbidden + files
        if not checker_args:
            raise PluginExecutionFailed("No arguments for the checker")

        run_args = RunScriptPlugin.Args(
            origin=str(args.reference_root / "build-relwithdebinfo"),
            script=[args.forbidden_checker, "-p", ".", *checker_args],
        )
        output = RunScriptPlugin()._run(run_args, verbose=verbose).output
        print_info(output)
        return PluginOutput(output="[No issues]")
