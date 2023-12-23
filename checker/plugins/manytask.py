from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, IO, Any

import requests
import requests.adapters
import urllib3
from pydantic import AnyUrl

from checker.exceptions import PluginExecutionFailed
from .base import PluginABC, PluginOutput


class ManytaskPlugin(PluginABC):
    """Given score report it to the manytask."""

    name = "report_score_manytask"
    _output: list[str]

    class Args(PluginABC.Args):
        origin: Optional[str] = None  # as pydantic does not support | in older python versions
        patterns: list[str] = ['*']
        username: str
        task_name: str
        score: float  # TODO: validate score is in [0, 1] (bonus score im higher than 1)
        report_url: AnyUrl
        tester_token: str
        check_deadline: bool
        send_time: datetime = datetime.now().astimezone()

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        # TODO: check on requests 2.0.0
        self._output = []
        # Do not expose token in logs.
        data = {
            'token': args.tester_token,
            'task': args.task_name,
            'username': args.username,
            'score': args.score,
            'check_deadline': args.check_deadline,
            'submit_time': self._format_time(args.send_time)
        }

        files = None
        if args.origin is not None:
            files = self._collect_files_to_send(args.origin, args.patterns)

        if verbose:
            self._output.append(str(files))

        response = self._post_with_retries(args.report_url, data, files)

        try:
            result = response.json()
            self._output.append(f"Report for task '{args.task_name}' for user '{args.username}', "
                                f"requested score: {args.score}, result score: {result['score']}")
            return PluginOutput(output='\n'.join(self._output))
        except (json.JSONDecodeError, KeyError):
            raise PluginExecutionFailed('Unable to decode response')

    @staticmethod
    def _post_with_retries(report_url: AnyUrl, data: dict[str, Any], files: dict[str, tuple[str, IO[bytes]]] | None) \
            -> requests.Response:
        retry_strategy = urllib3.Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[408, 500, 502, 503, 504]
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        response = session.post(url=f'{report_url}api/report', data=data, files=files)

        if response.status_code >= 400:
            raise PluginExecutionFailed(f'{response.status_code}: {response.text}')

        return response

    @staticmethod
    def _collect_files_to_send(origin: str, patterns: list[str]) -> dict[str, tuple[str, IO[bytes]]]:
        source_dir = Path(origin)
        return {
            path.name: (str(path.relative_to(source_dir)), open(path, 'rb'))
            for pattern in patterns
            for path in source_dir.glob(pattern)
            if path.is_file()
        }

    def _format_time(self, time: datetime) -> str:
        print(time)
        print(time.tzinfo)
        if not time.tzinfo:
            print(time.tzinfo)
            print(bool(time.tzinfo))
            self._output.append('Warning: No timezone provided for send_time, possible time miscalculations')
        time_isoformat = '%Y-%m-%dT%H:%M:%S.%f%:z'
        return time.strftime(time_isoformat)
