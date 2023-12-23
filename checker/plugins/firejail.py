from __future__ import annotations

import os

from .scripts import RunScriptPlugin


PATH = 'PATH'
PYTHONPATH = 'PYTHONPATH'


class SafeRunScriptPlugin(RunScriptPlugin):
    """Plugin for running scripts in safe mode."""

    name = "safe_run_script"

    Args = RunScriptPlugin.Args

    # TODO(uniqum): at the moment "--queit" option of firejail may stil put extra strings in the output
    def _run(self, args: Args, *, verbose: bool = False) -> str:
        whitelist_dir = args.origin if not args.origin.startswith('/tmp') else '~/tmp'
        command = ['firejail',
                   '--quiet',
                   '--noprofile',
                   # lock network access
                   '--net=none',
                   # allow access to origin dir
                   f'--whitelist={whitelist_dir}',
                   # hide all environment variables
                   'env -i',
                   # copy PATH
                   f'{PATH}={os.environ.get(PATH, "")}',
                   # cope PYTHONPATH
                   f'{PYTHONPATH}={os.environ.get(PYTHONPATH, "")}',
                   args.script if isinstance(args.script, str) else ' '.join(args.script),
                   ]
        run_args = RunScriptPlugin.Args(origin=args.origin, script=' '.join(command), timeout=args.timeout)

        return super()._run(args=run_args, verbose=verbose)
