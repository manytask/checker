from .base import PluginABC
from ..exceptions import ExecutionFailedError


class CheckRegexpsPlugin(PluginABC):
    """Plugin for checking forbidden regexps in a files."""

    name = "check_regexps"

    class Args(PluginABC.Args):
        origin: str
        patterns: list[str]
        regexps: list[str]

    def _run(self, args: Args, *, verbose: bool = False) -> str:
        import re
        from pathlib import Path

        if not Path(args.origin).exists():
            raise ExecutionFailedError(
                f"Origin {args.origin} does not exist",
                output=f"Origin {args.origin} does not exist",
            )

        for pattern in args.patterns:
            for file in Path(args.origin).glob(pattern):
                if file.is_file():
                    with file.open() as f:
                        file_content = f.read()

                    for regexp in args.regexps:
                        if re.search(regexp, file_content, re.MULTILINE):
                            raise ExecutionFailedError(
                                f"File {file} matches regexp {regexp}",
                                output=f"File {file} matches regexp {regexp}",
                            )
        return "No forbidden regexps found"
