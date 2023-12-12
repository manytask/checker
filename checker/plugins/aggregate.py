from __future__ import annotations

from typing import Literal

from .base import PluginABC
from ..exceptions import ExecutionFailedError


class AggregatePlugin(PluginABC):
    """Given scores and optional weights and strategy, aggregate them, return the score."""

    name = "aggregate"

    class Args(PluginABC.Args):
        scores: list[float]
        weights: list[float] | None = None
        strategy: Literal["mean", "sum", "min", "max", "product"] = "mean"

    def _run(self, args: Args, *, verbose: bool = False) -> str:
        weights = args.weights or [1.0] * len(args.scores)

        if len(args.scores) != len(args.weights):
            raise ExecutionFailedError(
                f"Length of scores ({len(args.scores)}) and weights ({len(weights)}) does not match",
                output=f"Length of scores ({len(args.scores)}) and weights ({len(weights)}) does not match",
            )

        weighted_scores = [score * weight for score, weight in zip(args.scores, weights)]

        if args.strategy == "mean":
            score = sum(weighted_scores) / len(weighted_scores)
        elif args.strategy == "sum":
            score = sum(weighted_scores)
        elif args.strategy == "min":
            score = min(weighted_scores)
        elif args.strategy == "max":
            score = max(weighted_scores)
        elif args.strategy == "product":
            from functools import reduce
            score = reduce(lambda x, y: x * y, weighted_scores)
        else:
            raise ExecutionFailedError(
                f"Unknown strategy {args.strategy}",
                output=f"Unknown strategy {args.strategy}",
            )

        return (
            f"Get scores:  {args.scores}\n"
            f"Get weights: {args.weights}\n"
            f"Aggregate weighted scores {weighted_scores} with strategy {args.strategy}\n"
            f"Score: {score:.2f}"
        )
