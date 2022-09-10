"""Helpers to interact with manytask (push scores tasks)"""
from __future__ import annotations

import io
import json
import time
from datetime import datetime

import requests

from ..exceptions import GetFailedError, PushFailedError


def push_report(
        report_base_url: str,
        tester_token: str,
        task_name: str,
        user_id: int,
        score: float,
        files: dict[str, tuple[str, io.BufferedReader]] | None = None,
        send_time: datetime | None = None,
        check_deadline: bool = True,
        use_demand_multiplier: bool = True,
) -> tuple[str, int, str | None, str | None, float | None]:
    # Do not expose token in logs.
    data = {
        'token': tester_token,
        'task': task_name,
        'user_id': user_id,
        'score': score,
        'check_deadline': check_deadline,
        'use_demand_multiplier': use_demand_multiplier,
    }
    if send_time:
        data['commit_time'] = send_time

    response = None
    for _ in range(3):
        response = requests.post(url=f'{report_base_url}/api/report', data=data, files=files)

        if response.status_code < 500:
            break
        time.sleep(1.0)
    assert response is not None

    if response.status_code >= 500:
        response.raise_for_status()
        assert False, 'Not Reachable'
    elif response.status_code >= 400:
        # Client error often means early submission
        raise PushFailedError(f'{response.status_code}: {response.text}')
    else:
        try:
            result = response.json()
            result_commit_time = result.get('commit_time', None)
            result_submit_time = result.get('submit_time', None)
            demand_multiplier = float(result.get('demand_multiplier', 1))
            return result['username'], result['score'], result_commit_time, result_submit_time, demand_multiplier
        except (json.JSONDecodeError, KeyError) as e:
            raise PushFailedError('Unable to decode response') from e


def get_score(
        report_base_url: str,
        tester_token: str,
        task_name: str,
        user_id: int,
) -> None:
    # Do not expose token in logs.
    data = {
        'token': tester_token,
        'task': task_name,
        'user_id': user_id,
    }
    # response = None
    for _ in range(3):
        response = requests.get(url=f'{report_base_url}/api/score', data=data)

        if response.status_code < 500:
            break
        time.sleep(1.0)

    if response.status_code >= 500:
        response.raise_for_status()
        assert False, 'Not Reachable'
        # print_info(f'{response.status_code}: {response.text}', color='orange')
    # Client error often means early submission
    elif response.status_code >= 400:
        raise GetFailedError(f'{response.status_code}: {response.text}')
        # print_info(f'{response.status_code}: {response.text}', color='orange')
    else:
        try:
            result = response.json()
            return result['score']
        except (json.JSONDecodeError, KeyError):
            # raise GetFailedError()
            pass

    return None
