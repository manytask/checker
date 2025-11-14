from __future__ import annotations

from pydantic import Field
from pathlib import Path
import re

from checker.plugins import PluginABC, PluginOutput
from checker.exceptions import PluginExecutionFailed
from checker.plugins.scripts import RunScriptPlugin


class RunPytestPlugin(RunScriptPlugin):
    """Plugin for running pytest."""

    name = "run_pytest"

    class Args(PluginABC.Args):
        origin: str
        target: str
        timeout: int | None = None
        isolate: bool = False
        env_whitelist: list[str] = Field(default_factory=lambda: ['PATH'])

        coverage: bool | int | None = None
        allow_failures: bool = False

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        tests_cmd = ['python', '-m', 'pytest']
        is_vm_task = args.target == "04.3.HW1/tasks/vm"

        if not verbose:
            tests_cmd += ['--no-header']
            tests_cmd += ['--tb=no']

        if args.coverage:
            tests_cmd += ['--cov-report', 'term-missing']
            tests_cmd += ['--cov', args.target]
            if args.coverage is not True:
                tests_cmd += ['--cov-fail-under', str(args.coverage)]
        else:
            tests_cmd += ['-p', 'no:cov']

        script_cmd = ' '.join(tests_cmd + [args.target])
        # For VM task, ensure pytest exit code doesn't raise; we'll parse output ourselves
        if is_vm_task:
            script_cmd = f"{script_cmd} || true"

        run_script_args = RunScriptPlugin.Args(
            origin=args.origin,
            script=script_cmd,
            timeout=args.timeout,
            isolate=args.isolate,
            env_whitelist=args.env_whitelist,
        )
        result = super()._run(run_script_args, verbose=verbose)
        # Parse score from stdout when VM task (no exception path due to '|| true')
        if is_vm_task:
            m = re.search(r"Summary score is:\s*([0-9]+(?:\.[0-9]+)?)", result.output or "")
            if m:
                score_val = float(m.group(1))
                scorer_path = Path(args.origin) / args.target / 'vm_scorer.py'
                text_sc = scorer_path.read_text(encoding='utf-8')
                m_full = re.search(r"FULL_SCORE\s*=\s*([0-9]+(?:\.[0-9]+)?)", text_sc)
                if m_full:
                    full = float(m_full.group(1))
                    if full > 0:
                        result.percentage = score_val / full
            else:
                result.percentage = 0
                
        return result
