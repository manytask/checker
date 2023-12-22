from __future__ import annotations

import json
import logging
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

    class Args(PluginABC.Args):
        origin: Optional[str] = None  # as pydantic does not support | in older python versions
        patterns: Optional[list[str]] = None  # as pydantic does not support | in older python versions
        username: str
        task_name: str
        score: float  # TODO: validate score is in [0, 1] (bonus score im higher than 1)
        report_url: AnyUrl
        tester_token: str
        check_deadline: bool
        send_time: datetime = datetime.now().astimezone()

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        # TODO: check on requests 2.0.0
        time_isoformat = '%Y-%m-%dT%H:%M:%S.%f%:z'
        # Do not expose token in logs.
        data = {
            'token': args.tester_token,
            'task': args.task_name,
            'username': args.username,
            'score': args.score,
            'check_deadline': args.check_deadline,
            'submit_time': args.send_time.strftime(time_isoformat)
        }

        files = self._collect_files_to_send(args)
        if verbose:
            logging.info(files)

        response = self._post_with_retries(args.report_url, data, files)

        try:
            result = response.json()
            return PluginOutput(
                f"Report for task '{args.task_name}' for user '{args.username}', "
                f"requested score: {args.score}, result score: {result['score']}"
            )
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
    def _collect_files_to_send(args: Args) -> dict[str, tuple[str, IO[bytes]]] | None:
        if args.origin is not None and args.patterns:
            source_dir = Path(args.origin)
            return {
                path.name: (str(path.relative_to(source_dir)), open(path, 'rb'))
                for pattern in args.patterns
                for path in source_dir.glob(pattern)
                if path.is_file()
            }

        return None
