from __future__ import annotations

from typing import Any
from datetime import datetime

from pytest_mock import MockFixture
import requests
import pytest
from pydantic import ValidationError

from checker.exceptions import PluginExecutionFailed
from checker.plugins.manytask import ManytaskPlugin


class TestManytaskPlugin:
    @pytest.mark.parametrize(
        "parameters, expected_exception",
        [
            ({
                 'username': 'user1',
                 'task_name': 'task1',
                 'score': 0.5,
                 'report_url': 'https://example.com',
                 'tester_token': 'token1',
                 'check_deadline': True
             }, None),
            ({
                 'origin': 'test/',
                 'patterns': ['*.py'],
                 'username': 'user2',
                 'task_name': 'task2',
                 'score': 0.01,
                 'report_url': 'https://example2.com',
                 'tester_token': 'token2',
                 'check_deadline': True,
                 'send_time': datetime.now()
             }, None),
            ({
                 'origin': '/test/test/test',
                 'patterns': ['*.py', '**.*', 'test'],
                 'username': 'user3',
                 'task_name': 'task3',
                 'score': 1.,
                 'report_url': 'https://example3.com',
                 'tester_token': 'token3',
                 'check_deadline': True,
                 'send_time': '2023-12-21T00:52:36.166028+06:00'
             }, None),
            ({
                 'origin': './',
                 'patterns': [],
                 'username': 'user4',
                 'task_name': 'task4',
                 'score': 1.5,
                 'report_url': 'https://example4.com',
                 'tester_token': 'token4',
                 'check_deadline': False
             }, None),
            ({
                 'origin': 'test/',
                 'patterns': ['*.py'],
                 'username': 'user2',
                 'task_name': 'task2',
                 'score': 0.01,
                 'report_url': 'invalidurl',
                 'tester_token': 'token2',
                 'check_deadline': True,
                 'send_time': datetime.now()
             }, ValidationError),
            ({
                 'origin': 'test/',
                 'patterns': ['*.py'],
                 'username': 'user2',
                 'task_name': 'task2',
                 'score': 0.01,
                 'report_url': 'https://example2.com',
                 'tester_token': 'token2',
                 'check_deadline': True,
                 'send_time': 'invalidtime'
             }, ValidationError),
            ({}, ValidationError),
        ],
    )
    def test_plugin_args(
            self, parameters: dict[str, Any], expected_exception: Exception | None
    ) -> None:
        if expected_exception:
            with pytest.raises(expected_exception):
                ManytaskPlugin.Args(**parameters)
        else:
            ManytaskPlugin.Args(**parameters)
