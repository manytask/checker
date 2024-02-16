from __future__ import annotations

from pathlib import Path

from checker.exceptions import PluginExecutionFailed
from checker.plugins.scripts import RunScriptPlugin
from checker.utils import print_info

from .base import PluginABC, PluginOutput


class CppClangFormatPlugin(PluginABC):
    name = "cpp_clang_format"

    class Args(PluginABC.Args):
        reference_root: Path
        task_path: Path
        lint_patterns: list[str]

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        lint_files = []
        for f in args.lint_patterns:
            lint_files += list(map(str, args.task_path.glob(f)))

        if not lint_files:
            raise PluginExecutionFailed("No files")

        run_args = RunScriptPlugin.Args(
            origin=str(args.reference_root), script=["./run-clang-format.py", "--color", "always", "-r", *lint_files]
        )
        output = RunScriptPlugin()._run(run_args, verbose=verbose).output
        print_info(output)
        return PluginOutput(output="[No issues]")
