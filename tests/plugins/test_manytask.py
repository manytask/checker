from __future__ import annotations

from datetime import datetime
from os.path import basename
from tempfile import TemporaryDirectory, NamedTemporaryFile
from typing import Any

import pytest
from pydantic import ValidationError, HttpUrl
from pytest_mock import MockFixture
from requests_mock import Mocker

from checker.plugins.manytask import ManytaskPlugin, PluginExecutionFailed


class TestManytaskPlugin:
    @staticmethod
    def get_sample_args() -> ManytaskPlugin.Args:
        return ManytaskPlugin.Args(username='user1',
                                   task_name='task1',
                                   score=0.5,
                                   report_url=HttpUrl('https://example.com'),
                                   tester_token='token1',
                                   check_deadline=True)

    @pytest.mark.parametrize(
        'parameters, expected_exception',
        [
            ({
                 'username': 'user1',
                 'task_name': 'task1',
                 'score': 0.5,
                 'report_url': 'https://example.com',
                 'tester_token': 'token1',
                 'check_deadline': True,
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

    def test_date_without_timezone_throws_warning(self) -> None:
        plugin = ManytaskPlugin()
        plugin._output = []
        plugin._format_time(datetime.now())
        assert any(output_str.startswith('Warning: No timezone') for output_str in plugin._output)

    def test_date_with_timezone_doesnt_throw_warning(self) -> None:
        plugin = ManytaskPlugin()
        plugin._output = []
        plugin._format_time(datetime.now().astimezone())
        assert not any(output_str.startswith('Warning: No timezone') for output_str in plugin._output)

    @pytest.mark.parametrize(
        'extensions_to_create, patterns_to_take, taken_files_num',
        [
            (['.py', '.yml', '.txt'],
             ['*'],
             3),
            (['.py', '.yml', '.txt'],
             ['*.py'],
             1),
            (['.py', '.yml', '.py', '.yml', '.txt'],
             ['*.py', '*.yml'],
             4),
            (['.py', '.yml', '.txt'],
             ['*.not'],
             0)
        ]
    )
    def test_collect_files_to_send(self, mocker: MockFixture, extensions_to_create: list[str],
                                   patterns_to_take: list[str],
                                   taken_files_num: int) -> None:

        with TemporaryDirectory() as tdir:
            tempfiles = []
            expected_filenames = []

            for extension in extensions_to_create:
                ntfile = NamedTemporaryFile(dir=tdir, suffix=extension)
                tempfiles.append(ntfile)
                if f'*{extension}' in patterns_to_take or '*' in patterns_to_take:
                    expected_filenames.append(basename(tempfiles[-1].name))

            mocker.patch('builtins.open', mocker.mock_open(read_data=b"File content"))
            result = ManytaskPlugin._collect_files_to_send(tdir, patterns_to_take)

            assert result is not None, "Didn't collect files"
            assert len(result) == taken_files_num, 'Wrong file quantity are collected'
            assert sorted(result.keys()) == sorted(expected_filenames), 'Wrong files are collected'

            if taken_files_num:
                open.assert_called_with(mocker.ANY, "rb")  # type: ignore

    @pytest.mark.parametrize(
        'response_status_code, response_text, expected_exception',
        [
            (200, 'Success', None),
            (408, 'Request Timeout', PluginExecutionFailed),
            (503, 'Service Unavailable', PluginExecutionFailed)
        ])
    def test_post_with_retries(self, response_status_code: int, response_text: str,
                               expected_exception: Exception) -> None:
        example_site = 'https://example.com'
        with Mocker() as mocker:
            mocker.post(f'{example_site}/api/report', status_code=response_status_code, text=response_text)

            if expected_exception:
                with pytest.raises(expected_exception) as exc:
                    ManytaskPlugin._post_with_retries(HttpUrl(example_site), {'key': 'value'}, None)
                assert str(response_status_code) in str(exc.value), "Status code wasn't provided in exception message"
                assert response_text in str(exc.value), "Error text wasn't provided in exception message"
            else:
                result = ManytaskPlugin._post_with_retries(HttpUrl(example_site), {'key': 'value'}, None)
                assert result.status_code == 200
                assert result.text == 'Success'
