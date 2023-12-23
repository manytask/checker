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
    BASE_URL = HttpUrl('https://test.manytask.org')
    TESTER_TOKEN = 'test_token'
    TEST_NOW_DATETIME = datetime(2021, 1, 1, 0, 0, 0, 1).astimezone()
    TEST_NOW_DATETIME_STR = '2023-12-21T00:52:36.166028+06:00'
    TEST_TASK_NAME = 'some_task'
    TEST_USERNAME = 'username'
    TEST_SCORE = 1.0

    @staticmethod
    def get_default_args_dict() -> dict[str, Any]:
        return {
            'username': TestManytaskPlugin.TEST_USERNAME,
            'task_name': TestManytaskPlugin.TEST_TASK_NAME,
            'score': TestManytaskPlugin.TEST_SCORE,
            'report_url': TestManytaskPlugin.BASE_URL,
            'tester_token': TestManytaskPlugin.TESTER_TOKEN,
            'check_deadline': True
        }

    @staticmethod
    def get_default_args() -> ManytaskPlugin.Args:
        return ManytaskPlugin.Args(**TestManytaskPlugin.get_default_args_dict())

    @pytest.mark.parametrize(
        'parameters, expected_exception',
        [
            ({}, None),
            ({
                 'origin': 'test/',
                 'patterns': ['*.py'],
             }, None),
            ({
                 'origin': '/test/test/test',
                 'patterns': ['*.py', '**.*', 'test'],
             }, None),
            ({
                 'origin': './',
             }, None),
            ({
                 'origin': '',
                 'patterns': [],
             }, None),
            ({
                 'score': 0.01,
             }, None),
            ({
                 'score': 1.,
             }, None),
            ({
                 'score': 1.5,
             }, None),
            ({
                 'send_time': TEST_NOW_DATETIME
             }, None),
            ({
                 'send_time': TEST_NOW_DATETIME_STR
             }, None),
            ({
                 'send_time': 'invalidtime'
             }, ValidationError),
            ({
                 'report_url': 'invalidurl'
             }, ValidationError),
        ],
    )
    def test_plugin_args(
            self, parameters: dict[str, Any], expected_exception: Exception | None
    ) -> None:
        args = self.get_default_args_dict()
        args.update(parameters)
        if expected_exception:
            with pytest.raises(expected_exception):
                ManytaskPlugin.Args(**args)
        else:
            ManytaskPlugin.Args(**args)

    def test_empty_args_raise_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskPlugin.Args(**{})

    def test_date_without_timezone_throws_warning(self) -> None:
        plugin = ManytaskPlugin()
        plugin._output = []
        plugin._format_time(self.TEST_NOW_DATETIME.replace(tzinfo=None))
        assert any(output_str.startswith('Warning: No timezone') for output_str in plugin._output)

    def test_date_with_timezone_doesnt_throw_warning(self) -> None:
        plugin = ManytaskPlugin()
        plugin._output = []
        plugin._format_time(self.TEST_NOW_DATETIME.astimezone())
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
        with Mocker() as mocker:
            mocker.post(f'{self.BASE_URL}api/report', status_code=response_status_code, text=response_text)

            if expected_exception:
                with pytest.raises(expected_exception) as exc:
                    ManytaskPlugin._post_with_retries(self.BASE_URL, {'key': 'value'}, None)
                assert str(response_status_code) in str(exc.value), "Status code wasn't provided in exception message"
                assert response_text in str(exc.value), "Error text wasn't provided in exception message"
            else:
                result = ManytaskPlugin._post_with_retries(self.BASE_URL, {'key': 'value'}, None)
                assert result.status_code == 200
                assert result.text == 'Success'
