from __future__ import annotations

from .base import PluginABC


class AggregatePlugin(PluginABC):
    """Given score report it to the manytask."""

    name = "report_score_manytask"

    class Args(PluginABC.Args):
        origin: str | None = None
        patterns: list[str] | None = None
        username: str
        task_name: str
        score: float  # TODO: validate score is in [0, 1] (bonus score?)

    def _run(self, args: Args, *, verbose: bool = False) -> str:
        # TODO: report score to the manytask
        return f"DRY_RUN: Report score {args.score} for task '{args.task_name}' for user '{args.username}'"
