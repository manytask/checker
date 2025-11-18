from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from pydantic import Field

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
        report_percentage: bool = True

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        # Use -I (isolated mode) to prevent sitecustomize.py and user site-packages
        # This blocks early monkey-patching attempts
        tests_cmd = ['python', '-I', '-m', 'pytest']

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

        # Use FIFO pipe for secure IPC to get test results as percentage
        # Only used when report_percentage=True (weighted test scoring)
        pipe_path = None
        report_data_holder = {'data': None, 'error': None}
        reader_thread = None

        try:
            if args.report_percentage:
                # Create a named pipe (FIFO) in temp directory
                # Use random name to make it harder to find (though still not perfect)
                temp_dir = Path(tempfile.gettempdir())
                pipe_path = temp_dir / f'checker_pipe_{os.getpid()}_{id(self)}'

                # Create FIFO pipe
                # Only owner can read/write
                os.mkfifo(str(pipe_path), mode=0o600)

                # Start reader thread BEFORE pytest starts
                reader_thread = threading.Thread(
                    target=self._read_pipe_data,
                    args=(pipe_path, report_data_holder),
                    daemon=True
                )
                reader_thread.start()

                # Use our secure plugin with pipe mode
                tests_cmd += ['-p', 'checker.plugins.checker_reporter']
                tests_cmd += ['--checker-report', str(pipe_path)]
                tests_cmd += ['--checker-use-pipe']

            script_cmd = ' '.join(tests_cmd + [args.target])

            if args.report_percentage:
                script_cmd = f"{script_cmd} || true"

            run_script_args = RunScriptPlugin.Args(
                origin=args.origin,
                script=script_cmd,
                timeout=args.timeout,
                isolate=args.isolate,
                env_whitelist=args.env_whitelist,
            )
            result = super()._run(run_script_args, verbose=verbose)

            if reader_thread:
                reader_thread.join(timeout=5.0)

            if args.report_percentage:
                report_data = report_data_holder.get('data')
                if report_data_holder.get('error'):
                    raise PluginExecutionFailed(
                        f"Failed to read report from pipe: {report_data_holder['error']}"
                    )
                elif not report_data:
                    raise PluginExecutionFailed(
                        "No report data received from pytest plugin"
                    )
                elif not isinstance(report_data, dict):
                    raise PluginExecutionFailed(
                        f"Invalid report data type: expected dict, got {type(report_data).__name__}"
                    )

                try:
                    summary = report_data.get('summary', {})
                    if not isinstance(summary, dict):
                        raise PluginExecutionFailed(
                            f"Invalid summary type: expected dict, got {type(summary).__name__}"
                        )

                    passed = summary.get('passed', 0)
                    total = summary.get('total', 0)

                    if not isinstance(passed, (int, float)) or not isinstance(total, (int, float)):
                        raise PluginExecutionFailed(
                            f"Invalid test counts: passed={passed!r}, total={total!r}"
                        )

                    if total > 0:
                        result.percentage = passed / total
                    else:
                        result.percentage = 0

                except KeyError as e:
                    raise PluginExecutionFailed(
                        f"Missing required field in report: {e}"
                    ) from e

            return result

        finally:
            # Clean up pipe file if it was created
            if pipe_path is not None and pipe_path.exists():
                try:
                    pipe_path.unlink()
                except OSError:
                    pass

    @staticmethod
    def _read_pipe_data(pipe_path: Path, result_holder: dict) -> None:
        """
        Read JSON data from pipe in a separate thread.
        Stores the last valid JSON line in result_holder['data'].
        Stores any error in result_holder['error'].
        """
        try:
            # Open pipe for reading (blocks until writer connects)
            with open(pipe_path, 'r', encoding='utf-8') as pipe:
                last_valid_data = None
                # Read all lines - last one wins (incremental updates)
                for line in pipe:
                    line = line.strip()
                    if line:
                        try:
                            last_valid_data = json.loads(line)
                        except json.JSONDecodeError:
                            # Skip malformed lines, keep previous valid data
                            pass

                result_holder['data'] = last_valid_data
        except Exception as e:
            result_holder['error'] = str(e)
